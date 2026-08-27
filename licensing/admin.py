from django.contrib import admin

from .models import License, LicenseDevice, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "max_sources",
        "max_destinations",
        "max_devices",
        "is_active",
    )
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "user",
        "plan",
        "status",
        "starts_at",
        "expires_at",
        "max_devices",
    )
    list_filter = ("status", "plan")
    search_fields = ("key", "user__username", "user__email")


@admin.register(LicenseDevice)
class LicenseDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "license",
        "device_id",
        "device_name",
        "is_active",
        "first_activated_at",
        "last_seen_at",
    )
    list_filter = ("is_active",)
    search_fields = (
        "device_id",
        "device_name",
        "license__key",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "payment",
        "status",
        "starts_at",
        "expires_at",
    )
    list_filter = ("status", "plan")
    search_fields = ("user__username", "user__email")
