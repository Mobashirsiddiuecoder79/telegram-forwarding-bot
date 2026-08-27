
from django.urls import path

from . import views

urlpatterns = [

    path(

        "",

        views.subscription_plans,

        name="subscription_plans",

    ),

    path(

        "create-order/<int:plan_id>/",

        views.create_payment_order,

        name="create_payment_order",

    ),

    path(

        "verify-payment/",

        views.verify_payment,

        name="verify_payment",

    ),

]

