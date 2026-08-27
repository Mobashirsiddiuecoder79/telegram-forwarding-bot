from django.shortcuts import render

from licensing.services import get_forwarding_quota


def home(request):
    quota = None

    if request.user.is_authenticated:
        quota = get_forwarding_quota(request.user)

    return render(
        request,
        "dashboard/home.html",
        {
            "quota": quota,
        },
    )
