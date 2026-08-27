from django.urls import path

from . import views


urlpatterns = [
    path(
        "webhook/",
        views.razorpay_webhook,
        name="razorpay_webhook",
    ),
    path(
        "create-order/<int:plan_id>/",
        views.create_order,
        name="create_order",
    ),
    path(
        "verify-payment/",
        views.verify_payment,
        name="verify_payment",
    ),
    path(
        "fail-payment/",
        views.fail_payment,
        name="fail_payment",
    ),
    path(
        "payment-failed/",
        views.payment_failed,
        name="payment_failed",
    ),
    path(
        "payments/",
        views.payment_history,
        name="payment_history",
    ),
]
