from django.urls import path

from .invite_views import InviteCodeListCreateView, InviteCodeToggleView

invite_urlpatterns = [
    path("invite-codes", InviteCodeListCreateView.as_view(), name="api-invite-codes"),
    path("invite-codes/<int:id>/toggle-status", InviteCodeToggleView.as_view(), name="api-invite-codes-toggle"),
]
