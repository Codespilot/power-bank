from django.urls import path

from .invite_views import InviteCodeListCreateView, InviteCodeToggleView
from .merchant_views import MerchantAssignAgentView, MerchantBatchAssignAgentView, MerchantHistoryListView, MerchantListView
from .profit_views import ProfitListView, ProfitTaskListView
from .views import HealthCheckView
from .user.user_views import TokenGrantView, TokenRefreshView
from .order_views import (
    OrderListView,
    OrderImportDetailView,
    OrderImportListCreateView,
    OrderImportRunProfitView,
    OrderImportRunningCountView,
)
from .wallet_views import WalletRecordListView, WalletView
from .withdraw_views import WithdrawApproveView, WithdrawCancelView, WithdrawListView, WithdrawRejectView

from .profile.profile_urls import profile_urlpatterns
from .user.user_urls import user_urlpatterns

urlpatterns = [
    path("health", HealthCheckView.as_view(), name="api-health"),

    path("token/grant", TokenGrantView.as_view(), name="api-token-grant"),
    path("token/refresh", TokenRefreshView.as_view(), name="api-token-refresh"),

    # 商户管理
    path("merchants", MerchantListView.as_view(), name="api-merchants-list"),
    path("merchants/allocate", MerchantBatchAssignAgentView.as_view(), name="api-merchants-batch-assign-agent"),
    path("merchants/<int:id>/history", MerchantHistoryListView.as_view(), name="api-merchants-history"),
    path("merchants/<int:id>/allocate", MerchantAssignAgentView.as_view(), name="api-merchants-assign-agent"),

    # 订单管理
    path("orders", OrderListView.as_view(), name="api-orders-list"),
    path("orders/import", OrderImportListCreateView.as_view(), name="api-order-imports-list-create"),
    path("orders/import/<int:id>", OrderImportDetailView.as_view(), name="api-order-imports-detail"),
    path("orders/import/<int:id>/run-profit", OrderImportRunProfitView.as_view(), name="api-order-imports-run-profit"),
    path("orders/import/running-count", OrderImportRunningCountView.as_view(), name="api-order-imports-running-count"),

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

# 用户管理
urlpatterns.extend(user_urlpatterns)

# 个人资料
urlpatterns.extend(profile_urlpatterns)
