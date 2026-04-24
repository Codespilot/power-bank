from django.urls import path

from .invite_views import InviteCodeView, InviteCodeToggleView

invite_urlpatterns = [
    path("invite-codes", InviteCodeView.as_view(), name="api-invite-codes-list-create"),
    path("invite-codes/<int:id>/toggle-status", InviteCodeToggleView.as_view(), name="api-invite-codes-toggle"),
]
