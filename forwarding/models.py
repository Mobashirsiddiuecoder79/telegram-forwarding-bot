from django.conf import settings
from django.db import models


class ForwardedMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forwarded_messages",
    )

    source_chat_id = models.BigIntegerField()
    source_message_id = models.BigIntegerField()

    destination_chat_id = models.BigIntegerField()

    forwarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "source_chat_id",
                    "source_message_id",
                    "destination_chat_id",
                ],
                name="unique_user_forwarded_message",
            )
        ]

    def __str__(self):
        return (
            f"{self.user} | "
            f"{self.source_chat_id}:{self.source_message_id} -> "
            f"{self.destination_chat_id}"
        )
