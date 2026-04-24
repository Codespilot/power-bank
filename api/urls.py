from django.urls import path

from .invite_views import InviteCodeListCreateView, InviteCodeToggleView

from .profit_views import ProfitListView, ProfitTaskListView
from .views import HealthCheckView
from .user.user_views import TokenGrantView, TokenRefreshView
from .wallet_views import WalletRecordListView, WalletView
from .withdraw_views import WithdrawApproveView, WithdrawCancelView, WithdrawListView, WithdrawRejectView

from .profile.profile_urls import profile_urlpatterns
from .user.user_urls import user_urlpatterns
from .order.order_urls import order_urlpatterns
from .merchant.merchant_urls import merchant_urlpatterns

urlpatterns = [
    # path("health", HealthCheckView.as_view(), name="api-health-check"),

    # 个人资料
    *profile_urlpatterns,

    # 用户管理
    *user_urlpatterns,

    # 订单管理
    *order_urlpatterns,

    path("token/grant", TokenGrantView.as_view(), name="api-token-grant"),
    path("token/refresh", TokenRefreshView.as_view(), name="api-token-refresh"),

    # 商户管理
    *merchant_urlpatterns,

    # 分润管理
    path("profits", ProfitListView.as_view(), name="api-profits-list"),
    path("profit-tasks", ProfitTaskListView.as_view(), name="api-profit-tasks-list"),

    # 邀请码管理
    path("invite-codes", InviteCodeListCreateView.as_view(), name="api-invite-codes"),
    path("invite-codes/<int:id>/toggle-status", InviteCodeToggleView.as_view(), name="api-invite-codes-toggle"),

    # 钱包管理
    path("wallet", WalletView.as_view(), name="api-wallet"),
    path("wallet/record", WalletRecordListView.as_view(), name="api-wallet-record"),

    # 提现管理
    path("withdraws", WithdrawListView.as_view(), name="api-withdraws"),
    path("withdraws/<int:id>/approve", WithdrawApproveView.as_view(), name="api-withdraws-approve"),
    path("withdraws/<int:id>/reject", WithdrawRejectView.as_view(), name="api-withdraws-reject"),
    path("withdraws/<int:id>/cancel", WithdrawCancelView.as_view(), name="api-withdraws-cancel"),
]
