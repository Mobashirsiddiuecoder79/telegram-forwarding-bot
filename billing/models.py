from django.conf import settings
from django.db import models


class Payment(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("expired", "Expired"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    # Plan purchased for this payment.
    # Nullable so existing payment records remain valid.
    plan = models.ForeignKey(
        "licensing.Plan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")

    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True,
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - ₹{self.amount} - {self.status}"
