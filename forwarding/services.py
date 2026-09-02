import asyncio
from datetime import datetime, timedelta

from telethon.tl.patched import Message
from telethon.errors import FloodWaitError
from asgiref.sync import sync_to_async
from django.core.cache import cache

from accounts.models import TelegramConnection
from accounts.services.telegram_client import get_telegram_client
from channels.models import ChannelPair
from forwarding.models import ForwardedMessage
from licensing.services import consume_forward_quota


async def forward_user_channels(user, max_messages=None):
    """
    Forward active channel pairs belonging ONLY to this Django user.

    No global Telegram session is used.
    No channels.json is used.
    """

    get_pairs = sync_to_async(
        lambda: list(
            ChannelPair.objects.filter(
                user=user,
                is_active=True,
            ).order_by("created_at")
        ),
        thread_sensitive=True,
    )

    pairs = await get_pairs()

    if not pairs:
        return {
            "pairs": 0,
            "forwarded": 0,
            "skipped": 0,
        }

    client = await sync_to_async(
        get_telegram_client,
        thread_sensitive=True,
    )(user)

    total_forwarded = 0
    total_skipped = 0

    await client.connect()

    try:
        if not await client.is_user_authorized():
            raise ValueError(
                "The connected Telegram session is no longer authorized."
            )

        for pair in pairs:
            if max_messages is not None and total_forwarded >= max_messages:
                break

            count = 0
            skipped = 0
            pair_limit = pair.message_limit

            async for message in client.iter_messages(
                pair.source_chat_id
            ):
                if max_messages is not None and total_forwarded >= max_messages:
                    break

                if pair_limit > 0 and count >= pair_limit:
                    break

                if cache.get(f"forwarding_stop_{user.id}"):
                    print(
                        f"{user.username}: forwarding stopped by user."
                    )
                    break

                if not isinstance(message, Message):
                    continue

                check_forwarded = sync_to_async(
                    lambda: ForwardedMessage.objects.filter(
                        user=user,
                        source_chat_id=pair.source_chat_id,
                        source_message_id=message.id,
                        destination_chat_id=pair.destination_chat_id,
                    ).exists(),
                    thread_sensitive=True,
                )

                already_forwarded = await check_forwarded()

                if already_forwarded:
                    skipped += 1
                    total_skipped += 1
                    continue

                if cache.get(f"forwarding_stop_{user.id}"):
                    print(
                        f"{user.username}: forwarding stopped by user."
                    )
                    break

                # Check STOP immediately before consuming quota.
                if cache.get(f"forwarding_stop_{user.id}"):
                    print(
                        f"{user.username}: forwarding stopped before quota consumption."
                    )
                    break

                # Never consume more than the requested amount.
                if (
                    max_messages is not None
                    and total_forwarded >= max_messages
                ):
                    break

                quota_available = await sync_to_async(
                    consume_forward_quota,
                    thread_sensitive=True,
                )(user, 1)

                if not quota_available:
                    print(
                        f"{user.username}: forwarding quota exhausted."
                    )
                    break

                try:
                    while True:
                        try:
                            await client.forward_messages(
                                pair.destination_chat_id,
                                message,
                            )
                            break

                        except FloodWaitError as exc:
                            now = datetime.now()
                            resume_time = now + timedelta(
                                seconds=exc.seconds + 5
                            )

                            print(
                                f"Telegram FloodWait for {user.username}: "
                                f"{exc.seconds}s"
                            )
                            print(
                                f"Resume at: "
                                f"{resume_time.strftime('%Y-%m-%d %I:%M:%S %p')}"
                            )

                            # Sleep in short intervals so STOP can
                            # interrupt a long Telegram FloodWait.
                            remaining_wait = exc.seconds + 5

                            while remaining_wait > 0:
                                if cache.get(
                                    f"forwarding_stop_{user.id}"
                                ):
                                    print(
                                        f"{user.username}: "
                                        "forwarding stopped during FloodWait."
                                    )
                                    return {
                                        "pairs": len(pairs),
                                        "forwarded": total_forwarded,
                                        "skipped": total_skipped,
                                    }

                                sleep_for = min(1, remaining_wait)
                                await asyncio.sleep(sleep_for)
                                remaining_wait -= sleep_for

                except Exception:
                    from licensing.services import release_forward_quota

                    await sync_to_async(
                        release_forward_quota,
                        thread_sensitive=True,
                    )(user, 1)

                    raise

                # The Telegram message was successfully forwarded.
                # Save it BEFORE checking STOP so it can never be
                # forwarded again on the next run.
                save_forwarded = sync_to_async(
                    lambda: ForwardedMessage.objects.get_or_create(
                        user=user,
                        source_chat_id=pair.source_chat_id,
                        source_message_id=message.id,
                        destination_chat_id=pair.destination_chat_id,
                    ),
                    thread_sensitive=True,
                )

                await save_forwarded()

                # This quota unit is legitimately consumed because
                # Telegram successfully forwarded the message.
                count += 1
                total_forwarded += 1

                # Check STOP only after the successful message has
                # been recorded in the database.
                if cache.get(f"forwarding_stop_{user.id}"):
                    print(
                        f"{user.username}: forwarding stopped after "
                        f"{total_forwarded} message(s)."
                    )
                    break

            print(
                f"{user.username}: "
                f"{pair.source_chat_id} -> "
                f"{pair.destination_chat_id} | "
                f"Forwarded: {count} | "
                f"Skipped: {skipped}"
            )

    finally:
        await client.disconnect()

    return {
        "pairs": len(pairs),
        "forwarded": total_forwarded,
        "skipped": total_skipped,
    }


async def check_user_channel_access(user):
    """
    Read-only check that the user's Telegram account can access
    every active source and destination channel.
    """

    def load_pairs():
        return list(
            ChannelPair.objects.filter(
                user=user,
                is_active=True,
            ).order_by("created_at")
        )

    pairs = await sync_to_async(
        load_pairs,
        thread_sensitive=True,
    )()

    if not pairs:
        return {
            "ok": False,
            "pairs": 0,
            "error": "No active channel pairs configured.",
        }

    client = await sync_to_async(
        get_telegram_client,
        thread_sensitive=True,
    )(user)

    await client.connect()

    try:
        if not await client.is_user_authorized():
            return {
                "ok": False,
                "pairs": len(pairs),
                "error": "Telegram session is no longer authorized.",
            }

        checked = []

        for pair in pairs:
            try:
                source = await client.get_entity(
                    pair.source_chat_id
                )

                destination = await client.get_entity(
                    pair.destination_chat_id
                )

            except Exception as exc:
                return {
                    "ok": False,
                    "pairs": len(pairs),
                    "error": (
                        f"Cannot access channel pair "
                        f"{pair.source_chat_id} -> "
                        f"{pair.destination_chat_id}: "
                        f"{exc}"
                    ),
                }

            checked.append({
                "source": pair.source_chat_id,
                "destination": pair.destination_chat_id,
                "source_accessible": source is not None,
                "destination_accessible": destination is not None,
            })

        return {
            "ok": True,
            "pairs": len(checked),
            "channels": checked,
        }

    finally:
        await client.disconnect()


async def dry_run_user_forwarding(user):
    """
    Validate the user's forwarding configuration without
    forwarding or modifying any Telegram messages.
    """

    access = await check_user_channel_access(user)

    if not access["ok"]:
        return access

    get_pairs = sync_to_async(
        lambda: list(
            ChannelPair.objects.filter(
                user=user,
                is_active=True,
            ).order_by("created_at")
        ),
        thread_sensitive=True,
    )

    pairs = await get_pairs()

    channels = [
        {
            "source": pair.source_chat_id,
            "destination": pair.destination_chat_id,
            "active": pair.is_active,
        }
        for pair in pairs
    ]

    return {
        "ok": True,
        "pairs": len(channels),
        "channels": channels,
    }


async def get_user_telegram_channels(user):
    """
    Return Telegram channels/groups accessible through THIS user's
    connected Telegram session.

    No other Django user's Telegram session is used.
    """

    connection_exists = await sync_to_async(
        lambda: TelegramConnection.objects.filter(
            user=user,
            is_connected=True,
            encrypted_session__isnull=False,
        ).exists(),
        thread_sensitive=True,
    )()

    if not connection_exists:
        return {
            "ok": False,
            "error": "Please connect your Telegram account first.",
            "channels": [],
        }

    client = await sync_to_async(
        get_telegram_client,
        thread_sensitive=True,
    )(user)

    await client.connect()

    try:
        if not await client.is_user_authorized():
            return {
                "ok": False,
                "error": "Your Telegram session is no longer authorized.",
                "channels": [],
            }

        channels = []

        async for dialog in client.iter_dialogs():
            entity = dialog.entity

            # Telegram channels and groups only.
            if not getattr(entity, "megagroup", False) and not getattr(
                entity, "broadcast", False
            ):
                continue

            channels.append(
                {
                    "id": entity.id,
                    "chat_id": (
                        int(f"-100{entity.id}")
                        if getattr(entity, "broadcast", False)
                        or getattr(entity, "megagroup", False)
                        else entity.id
                    ),
                    "title": dialog.name or "",
                    "username": getattr(entity, "username", None) or "",
                    "is_channel": bool(
                        getattr(entity, "broadcast", False)
                    ),
                    "is_group": bool(
                        getattr(entity, "megagroup", False)
                    ),
                }
            )

        return {
            "ok": True,
            "channels": channels,
        }

    finally:
        await client.disconnect()


async def check_user_channel_write_access(user, chat_id):
    """
    Check whether THIS user's Telegram account can post to the
    selected destination.

    This checks the destination only.
    It does not test or modify the source channel.
    It does not send a test message.
    """

    client = await sync_to_async(
        get_telegram_client,
        thread_sensitive=True,
    )(user)

    await client.connect()

    try:
        if not await client.is_user_authorized():
            return {
                "ok": False,
                "error": "Your Telegram session is no longer authorized.",
            }

        entity = await client.get_entity(chat_id)

        permissions = await client.get_permissions(
            entity,
            "me",
        )

        # Normal groups/supergroups.
        send_messages = getattr(
            permissions,
            "send_messages",
            None,
        )

        if send_messages is True:
            return {"ok": True}

        # Channels can expose posting ability through admin rights.
        admin_rights = getattr(
            permissions,
            "admin_rights",
            None,
        )

        if admin_rights:
            if getattr(
                admin_rights,
                "post_messages",
                False,
            ):
                return {"ok": True}

            if getattr(
                admin_rights,
                "anonymous",
                False,
            ):
                # Anonymous channel admins can still post.
                return {"ok": True}

        # Creator/owner has full control.
        if getattr(
            permissions,
            "is_creator",
            False,
        ):
            return {"ok": True}

        return {
            "ok": False,
            "error": (
                "Your Telegram account does not have permission "
                "to send messages to this destination."
            ),
        }

    finally:
        await client.disconnect()

