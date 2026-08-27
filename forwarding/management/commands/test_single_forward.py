import asyncio

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from telethon.errors import FloodWaitError

from accounts.services.telegram_client import get_telegram_client
from channels.models import ChannelPair
from forwarding.models import ForwardedMessage


async def forward_one(user, pair):
    client = await sync_to_async(
        get_telegram_client,
        thread_sensitive=True,
    )(user)

    await client.connect()

    try:
        if not await client.is_user_authorized():
            raise ValueError(
                "The Telegram session is no longer authorized."
            )

        message = None

        async for candidate in client.iter_messages(
            pair.source_chat_id,
            limit=10,
        ):
            if candidate:
                message = candidate
                break

        if message is None:
            return {
                "status": "empty",
                "message": "No messages found in the source channel.",
            }

        already_forwarded = await sync_to_async(
            lambda: ForwardedMessage.objects.filter(
                user=user,
                source_chat_id=pair.source_chat_id,
                source_message_id=message.id,
                destination_chat_id=pair.destination_chat_id,
            ).exists(),
            thread_sensitive=True,
        )()

        if already_forwarded:
            return {
                "status": "skipped",
                "message": (
                    f"Message {message.id} was already forwarded "
                    "to this destination."
                ),
            }

        try:
            await client.forward_messages(
                pair.destination_chat_id,
                message,
            )
        except FloodWaitError as exc:
            return {
                "status": "flood_wait",
                "message": (
                    f"Telegram requested a wait of {exc.seconds} seconds."
                ),
            }

        await sync_to_async(
            lambda: ForwardedMessage.objects.get_or_create(
                user=user,
                source_chat_id=pair.source_chat_id,
                source_message_id=message.id,
                destination_chat_id=pair.destination_chat_id,
            ),
            thread_sensitive=True,
        )()

        return {
            "status": "forwarded",
            "message_id": message.id,
            "message": (
                f"One message ({message.id}) was forwarded successfully."
            ),
        }

    finally:
        await client.disconnect()


class Command(BaseCommand):
    help = (
        "Forward exactly one recent message from a user's active "
        "Telegram channel pair."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            type=str,
        )

        parser.add_argument(
            "--pair-id",
            type=int,
            required=True,
        )

    def handle(self, *args, **options):
        username = options["username"]
        pair_id = options["pair_id"]

        try:
            user = User.objects.get(
                username=username,
            )
        except User.DoesNotExist:
            raise CommandError(
                f"Django user '{username}' does not exist."
            )

        try:
            pair = ChannelPair.objects.get(
                id=pair_id,
                user=user,
                is_active=True,
            )
        except ChannelPair.DoesNotExist:
            raise CommandError(
                "The selected channel pair does not exist, "
                "is inactive, or belongs to another user."
            )

        self.stdout.write(
            f"User: {username}"
        )

        self.stdout.write(
            f"Source: {pair.source_name} "
            f"({pair.source_chat_id})"
        )

        self.stdout.write(
            f"Destination: {pair.destination_name} "
            f"({pair.destination_chat_id})"
        )

        self.stdout.write(
            "Action: forwarding at most ONE recent message."
        )

        try:
            result = asyncio.run(
                forward_one(
                    user,
                    pair,
                )
            )
        except Exception as exc:
            raise CommandError(
                f"Single-message test failed: {exc}"
            )

        if result["status"] == "forwarded":
            self.stdout.write(
                self.style.SUCCESS(
                    result["message"]
                )
            )
        elif result["status"] == "skipped":
            self.stdout.write(
                self.style.WARNING(
                    result["message"]
                )
            )
        elif result["status"] == "empty":
            self.stdout.write(
                self.style.WARNING(
                    result["message"]
                )
            )
        elif result["status"] == "flood_wait":
            raise CommandError(
                result["message"]
            )
