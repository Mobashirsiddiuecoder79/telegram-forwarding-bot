import asyncio

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from forwarding.services import dry_run_user_forwarding


class Command(BaseCommand):
    help = "Safely test a user's Telegram forwarding configuration without forwarding messages."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            type=str,
            help="Django username to test",
        )

    def handle(self, *args, **options):
        username = options["username"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(
                f"Django user '{username}' does not exist."
            )

        self.stdout.write(
            f"Testing Telegram forwarding for: {username}"
        )

        try:
            result = asyncio.run(
                dry_run_user_forwarding(user)
            )
        except Exception as exc:
            raise CommandError(
                f"Dry-run failed: {exc}"
            )

        if not result.get("ok"):
            raise CommandError(
                result.get(
                    "error",
                    "Telegram forwarding configuration is invalid.",
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Telegram access: OK"
            )
        )

        self.stdout.write(
            f"Active channel pairs: {result['pairs']}"
        )

        for channel in result["channels"]:
            self.stdout.write(
                f"Source: {channel['source']} "
                f"-> Destination: {channel['destination']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "DRY RUN COMPLETE — NO MESSAGES FORWARDED"
            )
        )
