from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.shortcuts import redirect, render

from .forms import RegistrationForm, EditProfileForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
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
