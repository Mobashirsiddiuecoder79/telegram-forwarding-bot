from django.conf import settings
from django.db import models


class ChannelPair(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_pairs",
    )

    source_chat_id = models.BigIntegerField()
    destination_chat_id = models.BigIntegerField()

    source_name = models.CharField(max_length=255, blank=True)
    destination_name = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "source_chat_id",
                    "destination_chat_id",
                ],
                name="unique_user_channel_pair",
            )
        ]

    def __str__(self):
        return f"{self.source_chat_id} → {self.destination_chat_id}"
