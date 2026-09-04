from django.db import transaction
from django.utils import timezone

from .models import ForwardingUsage, Subscription


FREE_LIFETIME_LIMIT = 10


def get_active_subscription(user):
    now = timezone.now()

    return (
        Subscription.objects
        .select_related("plan")
        .filter(
            user=user,
            status="active",
            starts_at__lte=now,
            expires_at__gt=now,
            plan__is_active=True,
        )
        .order_by("-expires_at")
        .first()
    )


def get_forwarding_quota(user):
    """
    Return the user's current forwarding quota.

    Free:
        10 successful forwards for lifetime.

    Paid:
        Plan.max_daily_forwards per day.
    """

    # Admin/Superuser has unlimited forwarding.
    # Staff and normal users follow the existing quota rules.
    if user.is_superuser:
        return {
            "type": "paid",
            "limit": None,
            "used": 0,
            "remaining": None,
            "plan": "Business",
        }

    subscription = get_active_subscription(user)

    usage, _ = ForwardingUsage.objects.get_or_create(
        user=user
    )

    today = timezone.localdate()

    if usage.usage_date != today:
        usage.usage_date = today
        usage.daily_count = 0
        usage.save(
            update_fields=[
                "usage_date",
                "daily_count",
                "updated_at",
            ]
        )

    if subscription is None:
        remaining = max(
            FREE_LIFETIME_LIMIT - usage.free_lifetime_count,
            0,
        )

        return {
            "type": "free",
            "limit": FREE_LIFETIME_LIMIT,
            "used": usage.free_lifetime_count,
            "remaining": remaining,
            "plan": None,
        }

    daily_limit = subscription.plan.max_daily_forwards

    if daily_limit is None:
        return {
            "type": "paid",
            "limit": None,
            "used": usage.daily_count,
            "remaining": None,
            "plan": subscription.plan.name,
        }

    remaining = max(
        daily_limit - usage.daily_count,
        0,
    )

    return {
        "type": "paid",
        "limit": daily_limit,
        "used": usage.daily_count,
        "remaining": remaining,
        "plan": subscription.plan.name,
    }


@transaction.atomic
def consume_forward_quota(user, amount=1):
    """
    Reserve forwarding quota.

    Returns True if quota is available.

    The caller must call release_forward_quota() if the Telegram
    operation fails after quota reservation.
    """

    usage, _ = (
        ForwardingUsage.objects
        .select_for_update()
        .get_or_create(user=user)
    )

    today = timezone.localdate()

    if usage.usage_date != today:
        usage.usage_date = today
        usage.daily_count = 0

    # Admin/Superuser has unlimited forwarding.
    # Do not apply Free/Paid quota limits to admins.
    if user.is_superuser:
        usage.save(
            update_fields=[
                "usage_date",
                "daily_count",
                "free_lifetime_count",
                "updated_at",
            ]
        )
        return True

    subscription = get_active_subscription(user)

    if subscription is None:
        remaining = (
            FREE_LIFETIME_LIMIT
            - usage.free_lifetime_count
        )

        if remaining < amount:
            return False

        usage.free_lifetime_count += amount

    else:
        daily_limit = subscription.plan.max_daily_forwards

        if daily_limit is not None:
            remaining = (
                daily_limit
                - usage.daily_count
            )

            if remaining < amount:
                return False

        usage.daily_count += amount

    usage.save(
        update_fields=[
            "usage_date",
            "daily_count",
            "free_lifetime_count",
            "updated_at",
        ]
    )

    return True


@transaction.atomic
def release_forward_quota(user, amount=1):
    """
    Return reserved quota when a Telegram forwarding attempt fails.
    """

    usage = (
        ForwardingUsage.objects
        .select_for_update()
        .get(user=user)
    )

    # Admin/Superuser does not consume quota,
    # so there is nothing to release.
    if user.is_superuser:
        return

    subscription = get_active_subscription(user)

    if subscription is None:
        usage.free_lifetime_count = max(
            usage.free_lifetime_count - amount,
            0,
        )
    else:
        usage.daily_count = max(
            usage.daily_count - amount,
            0,
        )

    usage.save(
        update_fields=[
            "daily_count",
            "free_lifetime_count",
            "updated_at",
        ]
    )
