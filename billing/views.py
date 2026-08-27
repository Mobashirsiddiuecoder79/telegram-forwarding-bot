from decimal import Decimal

import json

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from licensing.models import Plan, Subscription
from .models import Payment


def _razorpay_client():
    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


@login_required
def create_order(request, plan_id):
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    plan = get_object_or_404(
        Plan,
        id=plan_id,
        is_active=True,
    )

    amount_paise = int(
        Decimal(plan.price) * Decimal("100")
    )

    if amount_paise <= 0:
        return JsonResponse(
            {"error": "This plan cannot be purchased online."},
            status=400,
        )

    client = _razorpay_client()

    try:
        order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"plan_{plan.id}_user_{request.user.id}",
                "notes": {
                    "user_id": str(request.user.id),
                    "plan_id": str(plan.id),
                },
            }
        )
    except Exception:
        return JsonResponse(
            {"error": "Unable to create Razorpay order."},
            status=502,
        )

    payment = Payment.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price,
        currency="INR",
        razorpay_order_id=order["id"],
        status="created",
    )

    return JsonResponse(
        {
            "key_id": settings.RAZORPAY_KEY_ID,
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "payment_id": payment.id,
            "plan_id": plan.id,
            "plan_name": plan.name,
        }
    )


@login_required
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    razorpay_order_id = request.POST.get(
        "razorpay_order_id"
    )
    razorpay_payment_id = request.POST.get(
        "razorpay_payment_id"
    )
    razorpay_signature = request.POST.get(
        "razorpay_signature"
    )
    plan_id = request.POST.get("plan_id")

    if not all(
        [
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            plan_id,
        ]
    ):
        return JsonResponse(
            {"error": "Incomplete payment information."},
            status=400,
        )

    payment = get_object_or_404(
        Payment,
        razorpay_order_id=razorpay_order_id,
        user=request.user,
    )

    plan = get_object_or_404(
        Plan,
        id=plan_id,
        is_active=True,
    )

    client = _razorpay_client()

    # ---------------------------------------------------------
    # 1. Verify Razorpay signature
    # ---------------------------------------------------------

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

        return JsonResponse(
            {"error": "Payment verification failed."},
            status=400,
        )
    except Exception:
        return JsonResponse(
            {"error": "Unable to verify payment."},
            status=502,
        )

    # ---------------------------------------------------------
    # 2. Verify the order directly with Razorpay
    # ---------------------------------------------------------

    try:
        razorpay_order = client.order.fetch(
            razorpay_order_id
        )
    except Exception:
        return JsonResponse(
            {"error": "Unable to verify Razorpay order."},
            status=502,
        )

    expected_amount_paise = int(
        payment.amount * Decimal("100")
    )

    if int(razorpay_order.get("amount", 0)) != expected_amount_paise:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {"error": "Razorpay order amount does not match."},
            status=400,
        )

    if razorpay_order.get("currency") != payment.currency:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {"error": "Razorpay order currency does not match."},
            status=400,
        )

    # ---------------------------------------------------------
    # 3. Verify payment directly with Razorpay
    # ---------------------------------------------------------

    try:
        razorpay_payment = client.payment.fetch(
            razorpay_payment_id
        )
    except Exception:
        return JsonResponse(
            {"error": "Unable to verify Razorpay payment."},
            status=502,
        )

    if razorpay_payment.get("order_id") != razorpay_order_id:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {"error": "Payment does not belong to this order."},
            status=400,
        )

    if int(razorpay_payment.get("amount", 0)) != expected_amount_paise:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {"error": "Payment amount does not match."},
            status=400,
        )

    if razorpay_payment.get("currency") != payment.currency:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {"error": "Payment currency does not match."},
            status=400,
        )

    if razorpay_payment.get("status") != "captured":
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {
                "error": "Payment has not been captured."
            },
            status=400,
        )

    # ---------------------------------------------------------
    # 4. Verify selected plan against our database payment
    # ---------------------------------------------------------

    if payment.amount != plan.price:
        payment.status = "failed"
        payment.save(update_fields=["status"])

        return JsonResponse(
            {
                "error": (
                    "Payment amount does not match "
                    "the selected plan."
                )
            },
            status=400,
        )

    # ---------------------------------------------------------
    # 5. Atomically mark payment paid + create subscription
    # ---------------------------------------------------------

    with transaction.atomic():

        payment = Payment.objects.select_for_update().get(
            pk=payment.pk
        )

        # Prevent duplicate subscription creation.
        if payment.status == "paid":
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment already verified.",
                }
            )

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

        now = timezone.now()

        # Expire subscriptions whose end date has passed.
        Subscription.objects.filter(
            user=request.user,
            status="active",
            expires_at__lte=now,
        ).update(status="expired")

        # Cancel existing active subscription.
        Subscription.objects.filter(
            user=request.user,
            status="active",
        ).update(status="cancelled")

        starts_at = now

        expires_at = now + timezone.timedelta(
            days=plan.duration_days
        )

        Subscription.objects.create(
            user=request.user,
            plan=plan,
            payment=payment,
            starts_at=starts_at,
            expires_at=expires_at,
            status="active",
        )

    return JsonResponse(
        {
            "success": True,
            "message": (
                f"{plan.name} activated successfully."
            ),
        }
    )


@login_required
def payment_failed(request):
    """
    Mark a Razorpay payment/order as failed.

    This endpoint is called by the frontend when Razorpay
    reports payment.failed.
    """

    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    razorpay_order_id = request.POST.get(
        "razorpay_order_id"
    )

    if not razorpay_order_id:
        return JsonResponse(
            {"error": "Order ID is required."},
            status=400,
        )

    payment = Payment.objects.filter(
        razorpay_order_id=razorpay_order_id,
        user=request.user,
    ).first()

    if not payment:
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    # Never overwrite an already successful payment.
    if payment.status == "paid":
        return JsonResponse(
            {
                "success": True,
                "status": "paid",
            }
        )

    payment.status = "failed"
    payment.save(update_fields=["status"])

    return JsonResponse(
        {
            "success": True,
            "status": "failed",
        }
    )


@login_required
def fail_payment(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    razorpay_order_id = request.POST.get("razorpay_order_id")

    if not razorpay_order_id:
        return JsonResponse(
            {"error": "Razorpay order ID is required."},
            status=400,
        )

    payment = Payment.objects.filter(
        razorpay_order_id=razorpay_order_id,
        user=request.user,
    ).first()

    if not payment:
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    # Do not change already completed payments.
    if payment.status == "paid":
        return JsonResponse(
            {
                "success": True,
                "message": "Payment was already completed.",
            }
        )

    if payment.status == "created":
        payment.status = "failed"
        payment.save(update_fields=["status"])

    return JsonResponse(
        {
            "success": True,
            "message": "Payment marked as failed.",
        }
    )


@login_required
def payment_history(request):
    payments = (
        Payment.objects
        .filter(user=request.user)
        .select_related(
            "subscription__plan"
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "billing/payment_history.html",
        {
            "payments": payments,
        },
    )


@csrf_exempt
def razorpay_webhook(request):
    """
    Receive and verify Razorpay webhook events.

    Supported events:
        payment.captured
        payment.failed
        refund.created
    """

    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    webhook_secret = getattr(
        settings,
        "RAZORPAY_WEBHOOK_SECRET",
        None,
    )

    if not webhook_secret:
        return JsonResponse(
            {"error": "Webhook secret is not configured."},
            status=500,
        )

    signature = request.headers.get(
        "X-Razorpay-Signature"
    )

    if not signature:
        return JsonResponse(
            {"error": "Missing webhook signature."},
            status=400,
        )

    try:
        client = _razorpay_client()

        client.utility.verify_webhook_signature(
            request.body.decode("utf-8"),
            signature,
            webhook_secret,
        )

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse(
            {"error": "Invalid webhook signature."},
            status=400,
        )

    except Exception:
        return JsonResponse(
            {"error": "Unable to verify webhook."},
            status=400,
        )

    try:
        payload = request.body.decode("utf-8")
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON payload."},
            status=400,
        )

    event = data.get("event")

    # ---------------------------------------------------------
    # PAYMENT CAPTURED
    # ---------------------------------------------------------

    if event == "payment.captured":

        payment_entity = (
            data
            .get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        razorpay_payment_id = payment_entity.get("id")
        razorpay_order_id = payment_entity.get("order_id")

        if not razorpay_payment_id or not razorpay_order_id:
            return JsonResponse(
                {"error": "Incomplete payment data."},
                status=400,
            )

        payment = (
            Payment.objects
            .select_related("plan", "user")
            .filter(
                razorpay_order_id=razorpay_order_id,
            )
            .first()
        )

        if not payment:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment record not found.",
                }
            )

        # Idempotency: already paid means nothing else to do.
        if payment.status == "paid":
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment already processed.",
                }
            )

        # Verify payment belongs to this order.
        if payment_entity.get("order_id") != payment.razorpay_order_id:
            return JsonResponse(
                {"error": "Payment/order mismatch."},
                status=400,
            )

        expected_amount_paise = int(
            payment.amount * Decimal("100")
        )

        if int(payment_entity.get("amount", 0)) != expected_amount_paise:
            payment.status = "failed"
            payment.save(update_fields=["status"])

            return JsonResponse(
                {"error": "Payment amount mismatch."},
                status=400,
            )

        if payment_entity.get("currency") != payment.currency:
            payment.status = "failed"
            payment.save(update_fields=["status"])

            return JsonResponse(
                {"error": "Payment currency mismatch."},
                status=400,
            )

        if payment_entity.get("status") != "captured":
            return JsonResponse(
                {"error": "Payment is not captured."},
                status=400,
            )

        if payment.plan is None:
            return JsonResponse(
                {
                    "error": "Payment has no associated plan."
                },
                status=400,
            )

        with transaction.atomic():

            payment = (
                Payment.objects
                .select_for_update()
                .select_related("plan", "user")
                .get(pk=payment.pk)
            )

            if payment.status == "paid":
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Payment already processed.",
                    }
                )

            payment.razorpay_payment_id = (
                razorpay_payment_id
            )
            payment.status = "paid"
            payment.paid_at = timezone.now()

            payment.save(
                update_fields=[
                    "razorpay_payment_id",
                    "status",
                    "paid_at",
                ]
            )

            now = timezone.now()

            Subscription.objects.filter(
                user=payment.user,
                status="active",
                expires_at__lte=now,
            ).update(status="expired")

            Subscription.objects.filter(
                user=payment.user,
                status="active",
            ).update(status="cancelled")

            Subscription.objects.create(
                user=payment.user,
                plan=payment.plan,
                payment=payment,
                starts_at=now,
                expires_at=(
                    now
                    + timezone.timedelta(
                        days=payment.plan.duration_days
                    )
                ),
                status="active",
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Payment captured and subscription activated.",
            }
        )

    # ---------------------------------------------------------
    # PAYMENT FAILED
    # ---------------------------------------------------------

    if event == "payment.failed":

        payment_entity = (
            data
            .get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        razorpay_order_id = payment_entity.get("order_id")
        razorpay_payment_id = payment_entity.get("id")

        if razorpay_order_id:
            payment = Payment.objects.filter(
                razorpay_order_id=razorpay_order_id,
            ).first()

            if payment and payment.status != "paid":

                if (
                    razorpay_payment_id
                    and not payment.razorpay_payment_id
                ):
                    payment.razorpay_payment_id = (
                        razorpay_payment_id
                    )
                    payment.save(
                        update_fields=[
                            "razorpay_payment_id"
                        ]
                    )

                payment.status = "failed"
                payment.save(
                    update_fields=["status"]
                )

        return JsonResponse(
            {
                "success": True,
                "message": "Payment failure synchronized.",
            }
        )

    # ---------------------------------------------------------
    # REFUND CREATED
    # ---------------------------------------------------------

    if event == "refund.created":

        payment_entity = (
            data
            .get("payload", {})
            .get("refund", {})
            .get("entity", {})
        )

        razorpay_payment_id = payment_entity.get(
            "payment_id"
        )

        if razorpay_payment_id:

            payment = Payment.objects.filter(
                razorpay_payment_id=razorpay_payment_id,
            ).first()

            if payment:

                payment.status = "refunded"

                payment.save(
                    update_fields=["status"]
                )

                Subscription.objects.filter(
                    payment=payment,
                    status="active",
                ).update(
                    status="cancelled"
                )

        return JsonResponse(
            {
                "success": True,
                "message": "Refund synchronized.",
            }
        )

    # Unknown events should still receive 200.
    return JsonResponse(
        {
            "success": True,
            "message": f"Event ignored: {event}",
        }
    )
