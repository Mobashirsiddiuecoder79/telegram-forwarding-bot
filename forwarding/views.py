import asyncio

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render

from accounts.models import TelegramConnection
from channels.models import ChannelPair
from licensing.services import (
    get_active_subscription,
    get_forwarding_quota,
)

from licensing.services import get_active_subscription, get_forwarding_quota

from .services import (
    check_user_channel_access,
    forward_user_channels,
)


@login_required
def forwarding_dashboard(request):
    pairs = list(
        ChannelPair.objects.filter(
            user=request.user
        ).order_by("-created_at")
    )

    connection = TelegramConnection.objects.filter(
        user=request.user,
        is_connected=True,
    ).first()

    # =========================
    # SERVER-SIDE PLAN CHECK
    # =========================

    subscription = get_active_subscription(request.user)

    # =========================
    # EFFECTIVE PLAN LIMITS
    # =========================
    # Free users do not have a Subscription row.
    # They still have the Free plan limits.

    if subscription is None:
        plan_name = "Free"
        max_sources = 1
        max_destinations = 1
    else:
        plan = subscription.plan
        plan_name = plan.name
        max_sources = plan.max_sources
        max_destinations = plan.max_destinations

    source_ids = {
        pair.source_chat_id
        for pair in pairs
    }

    destination_ids = {
        pair.destination_chat_id
        for pair in pairs
    }

    if len(source_ids) > max_sources:
        messages.error(
            request,
            (
                f"Your {plan_name} plan allows only "
                f"{max_sources} source channel"
                f"{'s' if max_sources != 1 else ''}. "
                "Please remove extra channels or upgrade your plan."
            ),
        )
        return redirect("forwarding_dashboard")

    if len(destination_ids) > max_destinations:
        messages.error(
            request,
            (
                f"Your {plan_name} plan allows only "
                f"{max_destinations} destination channel"
                f"{'s' if max_destinations != 1 else ''}. "
                "Please remove extra channels or upgrade your plan."
            ),
        )
        return redirect("forwarding_dashboard")

    quota = get_forwarding_quota(request.user)

    # Keep pair limits within the user's currently remaining quota.
    remaining_quota = quota["remaining"]
    for pair in pairs:
        if pair.message_limit > 0 and pair.message_limit > remaining_quota:
            pair.message_limit = remaining_quota
            pair.save(update_fields=["message_limit"])

    if request.method == "POST":
        pair_id = request.POST.get("pair_id")
        if pair_id:
            pair = ChannelPair.objects.filter(
                id=pair_id,
                user=request.user,
            ).first()

            if not pair:
                messages.error(request, "Invalid channel pair.")
                return redirect("forwarding_dashboard")

            try:
                message_limit = int(request.POST.get("message_limit", "0"))
            except (TypeError, ValueError):
                messages.error(request, "Enter a valid message limit.")
                return redirect("forwarding_dashboard")

            if message_limit < 0:
                messages.error(request, "Message limit cannot be negative.")
                return redirect("forwarding_dashboard")

            # A pair limit cannot exceed the user's remaining daily quota.
            if message_limit > 0 and message_limit > quota["remaining"]:
                message_limit = quota["remaining"]
                messages.info(
                    request,
                    f"Message limit was capped at your remaining quota of {message_limit} messages.",
                )

            pair.message_limit = message_limit
            pair.save(update_fields=["message_limit", "updated_at"])
            messages.success(request, "Channel pair limit updated successfully.")
            return redirect("forwarding_dashboard")

    return render(
        request,
        "forwarding/dashboard.html",
        {
            "channel_pairs": pairs,
            "connection": connection,
            "quota": quota,
        },
    )


@login_required
def stop_forwarding(request):
    if request.method != "POST":
        return redirect("forwarding_dashboard")

    running_key = f"forwarding_running_{request.user.id}"
    stop_key = f"forwarding_stop_{request.user.id}"

    if not cache.get(running_key):
        messages.info(
            request,
            "No forwarding job is currently running.",
        )
        return redirect("forwarding_dashboard")

    cache.set(
        stop_key,
        True,
        timeout=3600,
    )

    messages.warning(
        request,
        "Forwarding stop requested. The current message will finish, "
        "then forwarding will stop.",
    )

    return redirect("forwarding_dashboard")


@login_required
def start_forwarding(request):
    if request.method != "POST":
        return redirect("forwarding_dashboard")

    quota = get_forwarding_quota(request.user)

    if quota["remaining"] <= 0:
        messages.error(
            request,
            "Your forwarding quota has been exhausted.",
        )
        return redirect("forwarding_dashboard")

    requested_count = quota["remaining"]

    connection = TelegramConnection.objects.filter(
        user=request.user,
        is_connected=True,
    ).first()

    if not connection:
        messages.error(
            request,
            "Please connect your Telegram account first.",
        )
        return redirect("forwarding_dashboard")

    active_pairs_qs = ChannelPair.objects.filter(
        user=request.user,
        is_active=True,
    )

    active_pairs = active_pairs_qs.count()

    if active_pairs == 0:
        messages.error(
            request,
            "Please add at least one active channel pair first.",
        )
        return redirect("forwarding_dashboard")

    subscription = get_active_subscription(request.user)

    if subscription:
        max_sources = subscription.plan.max_sources
        max_destinations = subscription.plan.max_destinations
    else:
        max_sources = 1
        max_destinations = 1

    source_count = (
        active_pairs_qs
        .values("source_chat_id")
        .distinct()
        .count()
    )

    destination_count = (
        active_pairs_qs
        .values("destination_chat_id")
        .distinct()
        .count()
    )

    if source_count > max_sources:
        messages.error(
            request,
            (
                f"Your plan allows only {max_sources} source "
                f"channel{'s' if max_sources != 1 else ''}."
            ),
        )
        return redirect("forwarding_dashboard")

    if destination_count > max_destinations:
        messages.error(
            request,
            (
                f"Your plan allows only {max_destinations} destination "
                f"channel{'s' if max_destinations != 1 else ''}."
            ),
        )
        return redirect("forwarding_dashboard")

    # Prevent multiple forwarding jobs for the same user.
    running_key = f"forwarding_running_{request.user.id}"
    stop_key = f"forwarding_stop_{request.user.id}"

    if cache.get(running_key):
        messages.warning(
            request,
            "Forwarding is already running. Please stop the current job first.",
        )
        return redirect("forwarding_dashboard")

    # Clear any previous stop request and mark this job as running.
    cache.delete(stop_key)
    cache.set(running_key, True, timeout=3600)

    def run_forwarding():
        try:
            access = asyncio.run(
                check_user_channel_access(request.user)
            )

            if not access["ok"]:
                print(
                    f"{request.user.username}: "
                    f"Telegram access check failed: "
                    f"{access.get('error', 'Unknown error')}"
                )
                return

            result = asyncio.run(
                forward_user_channels(
                    request.user,
                    requested_count,
                )
            )

            print(
                f"{request.user.username}: "
                f"Forwarding finished. "
                f"Forwarded={result['forwarded']}, "
                f"Skipped={result['skipped']}"
            )

        except Exception as exc:
            print(
                f"{request.user.username}: "
                f"Forwarding failed: {exc}"
            )

        finally:
            cache.delete(
                f"forwarding_stop_{request.user.id}"
            )
            cache.delete(
                f"forwarding_running_{request.user.id}"
            )

    import threading

    threading.Thread(
        target=run_forwarding,
        daemon=True,
    ).start()

    messages.success(
        request,
        (
            f"Forwarding started for up to "
            f"{requested_count} messages."
        ),
    )

    return redirect("forwarding_dashboard")
    try:
        requested_count = int(request.POST.get("forward_count", "1"))
    except (TypeError, ValueError):
        messages.error(
            request,
            "Please enter a valid number of messages.",
        )
        return redirect("forwarding_dashboard")

    if requested_count < 1:
        messages.error(
            request,
            "Please enter at least 1 message.",
        )
        return redirect("forwarding_dashboard")

    quota = get_forwarding_quota(request.user)

    if requested_count > quota["remaining"]:
        messages.error(
            request,
            (
                f"You requested {requested_count} messages, "
                f"but only {quota['remaining']} messages remain "
                "in your forwarding quota."
            ),
        )
        return redirect("forwarding_dashboard")

    connection = TelegramConnection.objects.filter(
        user=request.user,
        is_connected=True,
    ).first()

    if not connection:
        messages.error(
            request,
            "Please connect your Telegram account first.",
        )
        return redirect("forwarding_dashboard")

    active_pairs_qs = ChannelPair.objects.filter(
        user=request.user,
        is_active=True,
    )

    active_pairs = active_pairs_qs.count()

    # Enforce the subscription's source/destination limits
    # before starting a forwarding job.
    subscription = get_active_subscription(request.user)

    if subscription:
        max_sources = subscription.plan.max_sources
        max_destinations = subscription.plan.max_destinations
    else:
        max_sources = 1
        max_destinations = 1

    source_count = (
        active_pairs_qs
        .values("source_chat_id")
        .distinct()
        .count()
    )

    destination_count = (
        active_pairs_qs
        .values("destination_chat_id")
        .distinct()
        .count()
    )

    if source_count > max_sources:
        messages.error(
            request,
            (
                f"Your plan allows only {max_sources} source "
                f"channel{'s' if max_sources != 1 else ''}."
            ),
        )
        return redirect("forwarding_dashboard")

    if destination_count > max_destinations:
        messages.error(
            request,
            (
                f"Your plan allows only {max_destinations} destination "
                f"channel{'s' if max_destinations != 1 else ''}."
            ),
        )
        return redirect("forwarding_dashboard")

    if active_pairs == 0:
        messages.error(
            request,
            "Please add at least one active channel pair first.",
        )
        return redirect("forwarding_dashboard")

    quota = get_forwarding_quota(request.user)

    if quota["remaining"] == 0:
        messages.error(
            request,
            "Your forwarding quota has been exhausted.",
        )
        return redirect("forwarding_dashboard")

    try:
        access = asyncio.run(
            check_user_channel_access(request.user)
        )

        if not access["ok"]:
            messages.error(
                request,
                access.get(
                    "error",
                    "Telegram channel access check failed.",
                ),
            )
            return redirect("forwarding_dashboard")

        result = asyncio.run(
            forward_user_channels(
                request.user,
                requested_count,
            )
        )

        messages.success(
            request,
            (
                f"Forwarding completed. "
                f"Pairs: {result['pairs']}, "
                f"Forwarded: {result['forwarded']}, "
                f"Skipped: {result['skipped']}."
            ),
        )

    except Exception as exc:
        messages.error(
            request,
            f"Forwarding failed: {exc}",
        )

    return redirect("forwarding_dashboard")
