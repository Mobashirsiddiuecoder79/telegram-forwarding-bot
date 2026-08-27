from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Payment


class Command(BaseCommand):
    help = "Expire unpaid Razorpay payment records older than 24 hours."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)

        payments = Payment.objects.filter(
            status="created",
            created_at__lt=cutoff,
        )

        count = payments.update(status="expired")

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Expired {count} abandoned payment(s)."
            )
        )
