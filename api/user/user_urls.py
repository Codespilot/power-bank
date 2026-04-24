from django.urls import path

from .user_views import UserAgentAssignView, LoginAPIView, RegisterAPIView, TokenGrantView, TokenRefreshView, UserListView, UserCreateView, UserDetailView, UserPasswordChangeView, UserPasswordResetView

user_urlpatterns = [
    path("users/login", LoginAPIView.as_view(), name="api-auth-login"),
    path("users/register", RegisterAPIView.as_view(), name="api-users-register"),
    path("users", UserListView.as_view(), name="api-users-list"),
    path("users/create", UserCreateView.as_view(), name="api-users-create"),
    path("users/<int:id>", UserDetailView.as_view(), name="api-users-detail"),
    path("users/<int:id>/assign-superior-agent", UserAgentAssignView.as_view(), name="api-users-assign-superior-agent"),
    path("users/<int:id>/reset-password", UserPasswordResetView.as_view(), name="api-users-reset-password"),
    path("users/agent", UserAgentAssignView.as_view(), name="api-agent"),
    path("users/change-password", UserPasswordChangeView.as_view(), name="api-profile-change-password"),
]
