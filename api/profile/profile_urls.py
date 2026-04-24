from django.urls import path

from .profile_views import UserProfileView

profile_urlpatterns = [
    path("profile", UserProfileView.as_view(), name="api-profile"),
]
