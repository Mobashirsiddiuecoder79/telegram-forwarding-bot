from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount",
        "currency",
        "status",
        "razorpay_order_id",
        "razorpay_payment_id",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "user__username",
        "user__email",
        "razorpay_order_id",
        "razorpay_payment_id",
    )
