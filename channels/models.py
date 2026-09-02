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
    message_limit = models.PositiveIntegerField(default=0, help_text="Maximum messages to forward for this channel pair. 0 means no pair-specific limit.")

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


class ForwardingRule(models.Model):
    channel_pair = models.OneToOneField(
        ChannelPair,
        on_delete=models.CASCADE,
        related_name='forwarding_rule',
    )

    enabled = models.BooleanField(default=False)

    # Keyword filtering
    keywords = models.TextField(blank=True)
    blocked_keywords = models.TextField(blank=True)

    # Content filtering
    allow_text = models.BooleanField(default=True)
    allow_photos = models.BooleanField(default=True)
    allow_videos = models.BooleanField(default=True)
    allow_documents = models.BooleanField(default=True)
    allow_audio = models.BooleanField(default=True)

    # Message filtering
    allow_forwarded = models.BooleanField(default=True)
    allow_normal = models.BooleanField(default=True)

    # Apply keyword rules to captions as well as text
    filter_captions = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Rules for {self.channel_pair}'
