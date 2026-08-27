from django.core.management.base import BaseCommand
from django.utils import timezone

from licensing.models import Subscription


class Command(BaseCommand):
    help = "Expire active subscriptions whose expiry time has passed."

    def handle(self, *args, **options):
        now = timezone.now()

        subscriptions = Subscription.objects.filter(
            status="active",
            expires_at__lte=now,
        )

        count = subscriptions.update(
            status="expired"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Expired {count} subscription(s)."
            )
        )
