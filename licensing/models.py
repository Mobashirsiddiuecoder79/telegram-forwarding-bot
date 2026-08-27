from django.conf import settings
from django.db import models


class Plan(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)

    max_sources = models.PositiveIntegerField(default=1)
    max_destinations = models.PositiveIntegerField(default=1)
    max_devices = models.PositiveIntegerField(default=1)

    # Maximum successful Telegram forwards allowed per day.
    # NULL means unlimited daily forwarding for this plan.
    max_daily_forwards = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class License(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
        ("revoked", "Revoked"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="licenses",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="licenses",
    )

    key = models.CharField(max_length=64, unique=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    max_devices = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.key}"


class LicenseDevice(models.Model):
    license = models.ForeignKey(
        License,
        on_delete=models.CASCADE,
        related_name="devices",
    )

    device_id = models.CharField(max_length=128)
    device_name = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)

    first_activated_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["license", "device_id"],
                name="unique_license_device",
            )
        ]

    def __str__(self):
        return f"{self.license.key} - {self.device_id}"


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    payment = models.OneToOneField(
        "billing.Payment",
        on_delete=models.PROTECT,
        related_name="subscription",
    )

    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.plan.name} - {self.status}"


class ForwardingUsage(models.Model):
    """
    Tracks forwarding usage for each Django user.

    daily_count:
        Successful forwards during the current usage day.

    free_lifetime_count:
        Successful forwards made while the user had no active
        paid subscription.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forwarding_usage",
    )

    usage_date = models.DateField(
        null=True,
        blank=True,
    )

    daily_count = models.PositiveIntegerField(
        default=0,
    )

    free_lifetime_count = models.PositiveIntegerField(
        default=0,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"daily={self.daily_count} - "
            f"free_lifetime={self.free_lifetime_count}"
        )
