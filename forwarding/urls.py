from django.urls import path

from . import views


urlpatterns = [
    path(
        "admin-monitoring/",
        views.admin_monitoring_dashboard,
        name="admin_monitoring_dashboard",
    ),
    path(
        "",
        views.forwarding_dashboard,
        name="forwarding_dashboard",
    ),
    path(
        "start/",
        views.start_forwarding,
        name="start_forwarding",
    ),
    path(
        "stop/",
        views.stop_forwarding,
        name="stop_forwarding",
    ),
]
