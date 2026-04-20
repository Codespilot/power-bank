from django.urls import path

from .invite_views import InviteCodeListCreateView, InviteCodeToggleView
from .merchant_views import MerchantAssignAgentView, MerchantBatchAssignAgentView, MerchantHistoryListView, MerchantListView
from .profile_views import CurrentUserPasswordView, CurrentUserProfileView
from .profit_views import ProfitListView
from .views import HealthCheckView, ItemListCreateView
from .user_views import AgentSaveView, LoginAPIView, RegisterAPIView, TokenGrantView, TokenRefreshView, UserListView, UserCreateView, UserDetailView, UserResetPasswordView
from .order_views import MerchantOrderListView, OrderImportListCreateView, OrderImportRunningCountView
from .wallet_views import WalletRecordListView, WalletView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="api-health"),
    path("items/", ItemListCreateView.as_view(), name="api-items"),
    path("auth/login/", LoginAPIView.as_view(), name="api-auth-login"),
    path("auth/register/", RegisterAPIView.as_view(), name="api-auth-register"),
    path("token/grant", TokenGrantView.as_view(), name="api-token-grant"),
    path("token/grant/", TokenGrantView.as_view()),
    path("token/refresh", TokenRefreshView.as_view(), name="api-token-refresh"),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("users/", UserListView.as_view(), name="api-users-list"),
    path("users/create/", UserCreateView.as_view(), name="api-users-create"),
    path("users/<int:id>/", UserDetailView.as_view(), name="api-users-detail"),
    path("users/<int:id>/assign-superior-agent/", AgentSaveView.as_view(), name="api-users-assign-superior-agent"),
    path("users/<int:id>/reset-password/", UserResetPasswordView.as_view(), name="api-users-reset-password"),
    path("agents/save/", AgentSaveView.as_view(), name="api-agents-save"),

    # 商户管理
    path("merchants/", MerchantListView.as_view(), name="api-merchants-list"),
    path("merchants/batch-assign-agent/", MerchantBatchAssignAgentView.as_view(), name="api-merchants-batch-assign-agent"),
    path("merchants/<int:id>/history/", MerchantHistoryListView.as_view(), name="api-merchants-history"),
    path("merchants/<int:id>/assign-agent/", MerchantAssignAgentView.as_view(), name="api-merchants-assign-agent"),

    # 订单管理
    path("orders/", MerchantOrderListView.as_view(), name="api-orders-list"),
    path("order-imports/", OrderImportListCreateView.as_view(), name="api-order-imports-list-create"),
    path("order-imports/running-count/", OrderImportRunningCountView.as_view(), name="api-order-imports-running-count"),

    # 分润管理
    path("profits/", ProfitListView.as_view(), name="api-profits-list"),

    # 邀请码管理
    path("invite-codes/", InviteCodeListCreateView.as_view(), name="api-invite-codes"),
    path("invite-codes/<int:id>/toggle-status/", InviteCodeToggleView.as_view(), name="api-invite-codes-toggle"),

    # 个人资料
    path("profile/", CurrentUserProfileView.as_view(), name="api-profile"),
    path("profile/change-password/", CurrentUserPasswordView.as_view(), name="api-profile-change-password"),

    # 钱包管理
    path("wallet", WalletView.as_view(), name="api-wallet"),
    path("wallet/", WalletView.as_view()),
    path("wallet/record", WalletRecordListView.as_view(), name="api-wallet-record"),
    path("wallet/record/", WalletRecordListView.as_view()),
]
