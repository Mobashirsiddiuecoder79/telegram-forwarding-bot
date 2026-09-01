import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import RegistrationForm, EditProfileForm
from .models import UserProfile


OTP_EXPIRY_MINUTES = 10


def _clear_pending_registration(request):
    request.session.pop("pending_registration", None)
    request.session.pop("pending_registration_otp_hash", None)
    request.session.pop("pending_registration_otp_expires", None)
    request.session.modified = True


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            cleaned = form.cleaned_data

            # Re-check uniqueness immediately before starting verification.
            username = cleaned["username"].strip()
            email = cleaned["email"].strip().lower()

            if User.objects.filter(username__iexact=username).exists():
                form.add_error(
                    "username",
                    "This username is already taken. Please choose another username.",
                )
                return render(
                    request,
                    "accounts/register.html",
                    {"form": form},
                )

            if User.objects.filter(email__iexact=email).exists():
                form.add_error(
                    "email",
                    "An account with this Gmail address already exists. Please use another email address.",
                )
                return render(
                    request,
                    "accounts/register.html",
                    {"form": form},
                )

            # Generate a secure 6-digit OTP.
            otp = f"{secrets.randbelow(1000000):06d}"

            # Store only temporary registration information.
            # NO User or UserProfile is created here.
            request.session["pending_registration"] = {
                "username": username,
                "full_name": cleaned["full_name"],
                "email": email,
                "phone_number": cleaned["phone_number"],
                "date_of_birth": cleaned["date_of_birth"].isoformat(),
                "password": cleaned["password1"],
            }

            request.session["pending_registration_otp_hash"] = (
                hashlib.sha256(otp.encode()).hexdigest()
            )

            request.session["pending_registration_otp_expires"] = (
                int(
                    (
                        timezone.now()
                        + timedelta(minutes=OTP_EXPIRY_MINUTES)
                    ).timestamp()
                )
            )

            request.session.modified = True

            try:
                send_mail(
                    "Verify your Telegram Forwarding Bot account",
                    (
                        f"Your email verification OTP is: {otp}\n\n"
                        f"This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.\n\n"
                        "If you did not create this account, you can ignore this email."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

            except Exception as exc:
                # IMPORTANT:
                # If email sending fails, remove the temporary
                # registration data. Nothing is saved as a user.
                _clear_pending_registration(request)

                form.add_error(
                    None,
                    f"Could not send the verification email. Please try again. ({exc})",
                )

                return render(
                    request,
                    "accounts/register.html",
                    {"form": form},
                )

            return redirect("verify_email")

    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


def verify_email(request):
    pending = request.session.get("pending_registration")
    otp_hash = request.session.get("pending_registration_otp_hash")
    expires_timestamp = request.session.get(
        "pending_registration_otp_expires"
    )

    if not pending or not otp_hash or not expires_timestamp:
        return redirect("register")

    expires_at = timezone.datetime.fromtimestamp(
        expires_timestamp,
        tz=timezone.get_current_timezone(),
    )

    if timezone.now() > expires_at:
        _clear_pending_registration(request)

        return render(
            request,
            "accounts/verify_email.html",
            {
                "email": pending.get("email", ""),
                "expired": True,
                "error": "Your verification code has expired. Please register again.",
            },
        )

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()

        if not otp:
            return render(
                request,
                "accounts/verify_email.html",
                {
                    "email": pending["email"],
                    "error": "Please enter the verification code.",
                },
            )

        submitted_hash = hashlib.sha256(
            otp.encode()
        ).hexdigest()

        if not secrets.compare_digest(
            submitted_hash,
            otp_hash,
        ):
            return render(
                request,
                "accounts/verify_email.html",
                {
                    "email": pending["email"],
                    "error": "Invalid verification code.",
                },
            )

        # Check again because another account could have been created
        # with the same username/email while this registration was pending.
        if User.objects.filter(
            username__iexact=pending["username"]
        ).exists():
            _clear_pending_registration(request)

            return render(
                request,
                "accounts/verify_email.html",
                {
                    "email": pending["email"],
                    "error": (
                        "This username is no longer available. "
                        "Please register again with another username."
                    ),
                },
            )

        if User.objects.filter(
            email__iexact=pending["email"]
        ).exists():
            _clear_pending_registration(request)

            return render(
                request,
                "accounts/verify_email.html",
                {
                    "email": pending["email"],
                    "error": (
                        "An account with this email already exists. "
                        "Please register again with another email address."
                    ),
                },
            )

        # ONLY AFTER successful OTP verification do we create the account.
        from datetime import date

        from django.db import transaction

        with transaction.atomic():
            user = User.objects.create_user(
                username=pending["username"],
                email=pending["email"],
                password=pending["password"],
            )

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": pending["full_name"],
                    "email": pending["email"],
                    "phone_number": pending["phone_number"],
                    "date_of_birth": date.fromisoformat(
                        pending["date_of_birth"]
                    ),
                    "email_verified": True,
                },
            )

        # Remove temporary registration information.
        _clear_pending_registration(request)

        # Log the newly verified user in.
        login(request, user)

        return redirect("home")

    return render(
        request,
        "accounts/verify_email.html",
        {
            "email": pending["email"],
            "expired": False,
        },
    )


@login_required
@never_cache
def profile(request):
    profile_data, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or "",
            "email": request.user.email,
            "phone_number": "",
        },
    )

    return render(
        request,
        "accounts/profile.html",
        {"profile": profile_data},
    )


@login_required
@never_cache
def edit_profile(request):
    profile_data, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.get_full_name() or "",
            "email": request.user.email,
            "phone_number": "",
        },
    )

    if request.method == "POST":
        form = EditProfileForm(
            request.POST,
            instance=profile_data,
            user=request.user,
        )

        if form.is_valid():
            form.save()
            return redirect("profile")
    else:
        form = EditProfileForm(
            instance=profile_data,
            user=request.user,
        )

    return render(
        request,
        "accounts/edit_profile.html",
        {"form": form},
    )
