import asyncio
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.models import TelegramConnection

from .models import ChannelPair
from forwarding.services import (
    check_user_channel_write_access,
    get_user_telegram_channels,
)
from licensing.services import get_active_subscription
from licensing.services import get_active_subscription


@login_required
def channel_management(request):

    # Telegram must be connected before managing channels.
    telegram_connection = TelegramConnection.objects.filter(
        user=request.user,
        is_connected=True,
    ).first()

    if not telegram_connection:
        messages.warning(
            request,
            "Please connect your Telegram account before managing channels.",
        )
        return redirect("telegram_connection")

    if request.method == "POST":
        source_chat_id = request.POST.get("source_chat_id", "").strip()
        destination_chat_id = request.POST.get("destination_chat_id", "").strip()
        source_name = request.POST.get("source_name", "").strip()
        destination_name = request.POST.get("destination_name", "").strip()

        if not source_chat_id or not destination_chat_id:
            messages.error(
                request,
                "Please select both source and destination channels.",
            )
        else:
            try:
                source_chat_id = int(source_chat_id)
                destination_chat_id = int(destination_chat_id)

                pair, created = ChannelPair.objects.get_or_create(
                    user=request.user,
                    source_chat_id=source_chat_id,
                    destination_chat_id=destination_chat_id,
                    defaults={
                        "source_name": source_name,
                        "destination_name": destination_name,
                        "is_active": True,
                    },
                )

                if created:
                    messages.success(
                        request,
                        "Channel pair added successfully.",
                    )
                    return redirect("forwarding_dashboard")

                messages.info(
                    request,
                    "This channel pair already exists.",
                )

            except ValueError:
                messages.error(
                    request,
                    "Invalid Telegram channel ID.",
                )

    channel_pairs = ChannelPair.objects.filter(
        user=request.user
    ).order_by("-created_at")

    telegram_result = asyncio.run(
        get_user_telegram_channels(request.user)
    )

    # Current plan limits for the Channels page.
    subscription = get_active_subscription(request.user)

    if subscription:
        current_plan = subscription.plan
    else:
        current_plan = None

    max_sources = current_plan.max_sources if current_plan else 1
    max_destinations = (
        current_plan.max_destinations
        if current_plan
        else 1
    )
    max_devices = current_plan.max_devices if current_plan else 1

    active_pairs = channel_pairs.filter(is_active=True)

    source_count = (
        active_pairs
        .values("source_chat_id")
        .distinct()
        .count()
    )

    destination_count = (
        active_pairs
        .values("destination_chat_id")
        .distinct()
        .count()
    )

    return render(
        request,
        "channels/management.html",
        {
            "channel_pairs": channel_pairs,
            "current_plan": current_plan,
            "max_sources": max_sources,
            "max_destinations": max_destinations,
            "max_devices": max_devices,
            "source_count": source_count,
            "destination_count": destination_count,
            "telegram_channels": telegram_result.get(
                "channels",
                [],
            ),
            "telegram_error": telegram_result.get("error"),
        },
    )

@login_required
def delete_channel_pair(request, pk):
    if request.method != "POST":
        return redirect("channel_management")

    pair = ChannelPair.objects.filter(
        pk=pk,
        user=request.user,
    ).first()

    if pair:
        pair.delete()
        messages.success(
            request,
            "Channel pair removed successfully.",
        )

    return redirect("channel_management")


@login_required
def toggle_channel_pair(request, pk):
    if request.method != "POST":
        return redirect("channel_management")

    pair = ChannelPair.objects.filter(
        pk=pk,
        user=request.user,
    ).first()

    if pair:
        pair.is_active = not pair.is_active
        pair.save(update_fields=["is_active", "updated_at"])

    return redirect("channel_management")


@login_required
def available_channels(request):
    if request.method != "GET":
        return redirect("channel_management")

    result = asyncio.run(
        get_user_telegram_channels(request.user)
    )

    return render(
        request,
        "channels/available.html",
        {
            "channels": result.get("channels", []),
            "error": result.get("error"),
        },
    )


@login_required
def add_selected_channel_pair(request):

    # Server-side protection:
    # a user cannot add channel pairs without a Telegram connection.
    telegram_connection = TelegramConnection.objects.filter(
        user=request.user,
        is_connected=True,
    ).first()

    if not telegram_connection:
        messages.warning(
            request,
            "Please connect your Telegram account before adding channels.",
        )
        return redirect("telegram_connection")

    if request.method != "POST":
        return redirect("channel_management")

    source_chat_id = request.POST.get(
        "source_chat_id",
        "",
    ).strip()

    destination_chat_id = request.POST.get(
        "destination_chat_id",
        "",
    ).strip()

    if not source_chat_id or not destination_chat_id:
        messages.error(
            request,
            "Please select both a source and destination channel.",
        )
        return redirect("channel_management")

    try:
        source_chat_id = int(source_chat_id)
        destination_chat_id = int(destination_chat_id)
    except ValueError:
        messages.error(
            request,
            "Invalid Telegram channel selection.",
        )
        return redirect("channel_management")

    try:
        result = asyncio.run(
            get_user_telegram_channels(request.user)
        )
    except Exception as exc:
        messages.error(
            request,
            f"Could not verify your Telegram channels: {exc}",
        )
        return redirect("channel_management")

    if not result.get("ok"):
        messages.error(
            request,
            result.get(
                "error",
                "Could not access your Telegram account.",
            ),
        )
        return redirect("channel_management")

    available = {
        int(channel["chat_id"]): channel
        for channel in result.get("channels", [])
    }

    source = available.get(source_chat_id)
    destination = available.get(destination_chat_id)

    if not source or not destination:
        messages.error(
            request,
            "One or both selected channels are not accessible from your Telegram account.",
        )
        return redirect("channel_management")

    # Verify that THIS user's Telegram account can write to
    # the selected destination before creating the pair.
    try:
        permission = asyncio.run(
            check_user_channel_write_access(
                request.user,
                destination_chat_id,
            )
        )
    except Exception as exc:
        messages.error(
            request,
            f"Could not verify destination permissions: {exc}",
        )
        return redirect("channel_management")

    if not permission.get("ok"):
        messages.error(
            request,
            permission.get(
                "error",
                "You cannot send messages to this destination.",
            ),
        )
        return redirect("channel_management")

    # Enforce source/destination limits from the user's active plan.
    subscription = get_active_subscription(request.user)

    if subscription:
        max_sources = subscription.plan.max_sources
        max_destinations = subscription.plan.max_destinations
    else:
        # Free users get the same basic 1/1 channel allowance.
        max_sources = 1
        max_destinations = 1

    existing_pairs = ChannelPair.objects.filter(
        user=request.user,
        is_active=True,
    )

    existing_sources = (
        existing_pairs
        .values("source_chat_id")
        .distinct()
        .count()
    )

    existing_destinations = (
        existing_pairs
        .values("destination_chat_id")
        .distinct()
        .count()
    )

    source_already_used = existing_pairs.filter(
        source_chat_id=source_chat_id
    ).exists()

    destination_already_used = existing_pairs.filter(
        destination_chat_id=destination_chat_id
    ).exists()

    if (
        not source_already_used
        and existing_sources >= max_sources
    ):
        messages.error(
            request,
            (
                f"Your plan allows a maximum of "
                f"{max_sources} source channel"
                f"{'s' if max_sources != 1 else ''}. "
                f"Please upgrade your plan to add more."
            ),
        )
        return redirect("channel_management")

    if (
        not destination_already_used
        and existing_destinations >= max_destinations
    ):
        messages.error(
            request,
            (
                f"Your plan allows a maximum of "
                f"{max_destinations} destination channel"
                f"{'s' if max_destinations != 1 else ''}. "
                f"Please upgrade your plan to add more."
            ),
        )
        return redirect("channel_management")

    # =========================
    # PLAN LIMIT ENFORCEMENT
    # =========================

    subscription = get_active_subscription(request.user)

    if subscription is None:
        messages.error(
            request,
            "Your Free plan does not allow adding channel pairs. "
            "Please upgrade your plan to continue.",
        )
        return redirect("channel_management")

    plan = subscription.plan

    existing_pairs = ChannelPair.objects.filter(
        user=request.user,
        is_active=True,
    )

    # Count unique active source channels.
    existing_sources = set(
        existing_pairs.values_list(
            "source_chat_id",
            flat=True,
        )
    )

    # Count unique active destination channels.
    existing_destinations = set(
        existing_pairs.values_list(
            "destination_chat_id",
            flat=True,
        )
    )

    # Only increase the count if this channel is new.
    new_source_count = len(existing_sources)
    if source_chat_id not in existing_sources:
        new_source_count += 1

    new_destination_count = len(existing_destinations)
    if destination_chat_id not in existing_destinations:
        new_destination_count += 1

    if new_source_count > plan.max_sources:
        messages.error(
            request,
            (
                f"{plan.name} allows a maximum of "
                f"{plan.max_sources} source channel"
                f"{'s' if plan.max_sources != 1 else ''}. "
                "Please upgrade your plan to add more."
            ),
        )
        return redirect("channel_management")

    if new_destination_count > plan.max_destinations:
        messages.error(
            request,
            (
                f"{plan.name} allows a maximum of "
                f"{plan.max_destinations} destination channel"
                f"{'s' if plan.max_destinations != 1 else ''}. "
                "Please upgrade your plan to add more."
            ),
        )
        return redirect("channel_management")

    pair, created = ChannelPair.objects.get_or_create(
        user=request.user,
        source_chat_id=source_chat_id,
        destination_chat_id=destination_chat_id,
        defaults={
            "source_name": source["title"],
            "destination_name": destination["title"],
            "is_active": True,
        },
    )

    if created:
        messages.success(
            request,
            "Telegram channel pair added successfully.",
        )
    else:
        if not pair.is_active:
            pair.is_active = True
            pair.source_name = source["title"]
            pair.destination_name = destination["title"]
            pair.save(
                update_fields=[
                    "is_active",
                    "source_name",
                    "destination_name",
                    "updated_at",
                ],
            )

            messages.success(
                request,
                "Telegram channel pair reactivated successfully.",
            )
        else:
            messages.info(
                request,
                "This channel pair already exists.",
            )

    return redirect("channel_management")
