from django.contrib import admin

from .models import ChannelPair


@admin.register(ChannelPair)
class ChannelPairAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "source_chat_id",
        "destination_chat_id",
        "source_name",
        "destination_name",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = (
        "source_name",
        "destination_name",
        "user__username",
        "user__email",
    )
