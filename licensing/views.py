from decimal import Decimal

import razorpay

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.models import Payment

from .models import Plan, Subscription
from .services import get_active_subscription, get_forwarding_quota


@login_required
def subscription_plans(request):
    plans = Plan.objects.filter(
        is_active=True
    ).order_by("price")

    quota = get_forwarding_quota(request.user)

    current_subscription = get_active_subscription(request.user)

    active_plan = (
        current_subscription.plan
        if current_subscription
        else None
    )

    return render(
        request,
        "licensing/plans.html",
        {
            "plans": plans,
            "quota": quota,
            "active_plan": active_plan,
            "current_subscription": current_subscription,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        },
    )


@login_required
@require_POST
def create_payment_order(request, plan_id):
    """
    Create a Razorpay order and a local pending Payment.

    The plan and amount are obtained from the database.
    Nothing from the browser is trusted for pricing.
    """

    plan = get_object_or_404(
        Plan,
        id=plan_id,
        is_active=True,
    )

    # Do not allow upgrading to the currently active plan.
    active_subscription = get_active_subscription(request.user)

    if (
        active_subscription
        and active_subscription.plan_id == plan.id
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "This is already your active plan.",
            },
            status=400,
        )

    amount = Decimal(plan.price)

    if amount <= 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "This plan cannot be purchased.",
            },
            status=400,
        )

    amount_paise = int(amount * Decimal("100"))

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )

    try:
        razorpay_order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": (
                    f"u{request.user.id}-"
                    f"p{plan.id}-"
                    f"{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
                ),
                "notes": {
                    "user_id": str(request.user.id),
                    "plan_id": str(plan.id),
                },
            }
        )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": "Unable to create payment order.",
            },
            status=502,
        )

    Payment.objects.create(
        user=request.user,
        amount=amount,
        currency="INR",
        razorpay_order_id=razorpay_order["id"],
        status="created",
    )

    return JsonResponse(
        {
            "ok": True,
            "key_id": settings.RAZORPAY_KEY_ID,
            "order_id": razorpay_order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "plan_id": plan.id,
            "plan_name": plan.name,
        }
    )


@login_required
@require_POST
def verify_payment(request):
    """
    Verify the Razorpay payment SERVER-SIDE.

    Subscription is created only after successful verification.
    """

    razorpay_order_id = request.POST.get(
        "razorpay_order_id",
        "",
    ).strip()

    razorpay_payment_id = request.POST.get(
        "razorpay_payment_id",
        "",
    ).strip()

    razorpay_signature = request.POST.get(
        "razorpay_signature",
        "",
    ).strip()

    if not all(
        [
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
        ]
    ):
        messages.error(
            request,
            "Incomplete payment verification data.",
        )
        return redirect("subscription_plans")

    try:
        payment = Payment.objects.get(
            razorpay_order_id=razorpay_order_id,
            user=request.user,
        )
    except Payment.DoesNotExist:
        messages.error(
            request,
            "Payment order was not found.",
        )
        return redirect("subscription_plans")

    if payment.status == "paid":
        messages.info(
            request,
            "This payment has already been processed.",
        )
        return redirect("subscription_plans")

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        messages.error(
            request,
            "Payment verification failed.",
        )
        return redirect("subscription_plans")

    # Retrieve the Razorpay order server-side.
    try:
        order = client.order.fetch(
            razorpay_order_id
        )
    except Exception:
        messages.error(
            request,
            "Unable to verify the payment order.",
        )
        return redirect("subscription_plans")

    # Amount is checked against our local Payment record.
    expected_amount = int(
        payment.amount * Decimal("100")
    )

    if int(order.get("amount", 0)) != expected_amount:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        messages.error(
            request,
            "Payment amount verification failed.",
        )
        return redirect("subscription_plans")

    if order.get("currency") != payment.currency:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        messages.error(
            request,
            "Payment currency verification failed.",
        )
        return redirect("subscription_plans")

    # Determine the plan from the Razorpay order notes,
    # then verify that the plan price matches our database.
    try:
        plan_id = int(
            order.get("notes", {}).get("plan_id")
        )
        plan = Plan.objects.get(
            id=plan_id,
            is_active=True,
        )
    except (
        TypeError,
        ValueError,
        Plan.DoesNotExist,
    ):
        messages.error(
            request,
            "Unable to identify the purchased plan.",
        )
        return redirect("subscription_plans")

    if Decimal(plan.price) != payment.amount:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        messages.error(
            request,
            "Plan price verification failed.",
        )
        return redirect("subscription_plans")

    try:
        payment_data = client.payment.fetch(
            razorpay_payment_id
        )
    except Exception:
        messages.error(
            request,
            "Unable to verify payment status.",
        )
        return redirect("subscription_plans")

    if payment_data.get("order_id") != razorpay_order_id:
        messages.error(
            request,
            "Payment order mismatch.",
        )
        return redirect("subscription_plans")

    if payment_data.get("status") != "captured":
        messages.error(
            request,
            "Payment has not been captured.",
        )
        return redirect("subscription_plans")

    if int(payment_data.get("amount", 0)) != expected_amount:
        messages.error(
            request,
            "Captured payment amount does not match.",
        )
        return redirect("subscription_plans")

    # =========================
    # PAYMENT + SUBSCRIPTION
    # =========================

    with transaction.atomic():
        payment = (
            Payment.objects
            .select_for_update()
            .get(pk=payment.pk)
        )

        # Prevent duplicate callback processing.
        if payment.status == "paid":
            return redirect("subscription_plans")

        payment.razorpay_payment_id = (
            razorpay_payment_id
        )
        payment.razorpay_signature = (
            razorpay_signature
        )
        payment.status = "paid"
        payment.paid_at = timezone.now()

        payment.save(
            update_fields=[
                "razorpay_payment_id",
                "razorpay_signature",
                "status",
                "paid_at",
            ]
        )

        # Expire the user's previous active subscription.
        Subscription.objects.filter(
            user=request.user,
            status="active",
        ).update(
            status="expired",
        )

        starts_at = timezone.now()
        expires_at = (
            starts_at
            + timezone.timedelta(
                days=plan.duration_days
            )
        )

        Subscription.objects.create(
            user=request.user,
            plan=plan,
            payment=payment,
            starts_at=starts_at,
            expires_at=expires_at,
            status="active",
        )

    messages.success(
        request,
        f"{plan.name} activated successfully.",
    )

    return redirect("subscription_plans")
