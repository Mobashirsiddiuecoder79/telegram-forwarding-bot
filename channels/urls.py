from django.urls import path

from . import views


urlpatterns = [
    path(
        "add-selected/",
        views.add_selected_channel_pair,
        name="add_selected_channel_pair",
    ),
    path(
        "available/",
        views.available_channels,
        name="available_channels",
    ),
    path(
        "",
        views.channel_management,
        name="channel_management",
    ),
    path(
        "<int:pk>/delete/",
        views.delete_channel_pair,
        name="delete_channel_pair",
    ),
    path(
        "<int:pk>/toggle/",
        views.toggle_channel_pair,
        name="toggle_channel_pair",
    ),
]
