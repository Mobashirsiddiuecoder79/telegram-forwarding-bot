from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.decorators.cache import never_cache

from . import views
from .views import register
from .telegram_views import (
    telegram_connection,
    telegram_send_code,
    telegram_verify_code,
    telegram_verify_2fa,
    telegram_disconnect,
)


urlpatterns = [
    path(
        "telegram/",
        telegram_connection,
        name="telegram_connection",
    ),

    path(
        "telegram/send-code/",
        telegram_send_code,
        name="telegram_send_code",
    ),

    path(
        "telegram/verify-code/",
        telegram_verify_code,
        name="telegram_verify_code",
    ),

    path(
        "telegram/verify-2fa/",
        telegram_verify_2fa,
        name="telegram_verify_2fa",
    ),

    path(
        "telegram/disconnect/",
        telegram_disconnect,
        name="telegram_disconnect",
    ),
    path(
        "profile/",
        views.profile,
        name="profile",
    ),

    path(
        "profile/edit/",
        views.edit_profile,
        name="profile_edit",
    ),

    path(
        "password-change/",
        never_cache(auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/accounts/password-change/done/",
        )),
        name="password_change",
    ),

    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),

    path(
        "register/",
        register,
        name="register",
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url="/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),

    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),

    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),

    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
