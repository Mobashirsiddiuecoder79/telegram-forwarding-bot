from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    date_of_birth = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name


class TelegramConnection(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_connection",
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True,
    )

    telegram_user_id = models.BigIntegerField(
        null=True,
        blank=True,
    )

    telegram_username = models.CharField(
        max_length=255,
        blank=True,
    )

    first_name = models.CharField(
        max_length=255,
        blank=True,
    )

    last_name = models.CharField(
        max_length=255,
        blank=True,
    )

    is_connected = models.BooleanField(
        default=False,
    )

    # Encrypted Telethon session.
    # Never expose this value to normal users.
    encrypted_session = models.TextField(
        blank=True,
    )

    connected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        if self.telegram_username:
            return f"{self.user.username} → @{self.telegram_username}"

        if self.phone_number:
            return f"{self.user.username} → {self.phone_number}"

        return f"{self.user.username} → Telegram"
