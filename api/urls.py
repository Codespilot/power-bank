from django.urls import path

from .profit_views import ProfitListView, ProfitTaskListView
from .views import HealthCheckView
from .user.user_views import TokenGrantView, TokenRefreshView

from .profile.profile_urls import profile_urlpatterns
from .user.user_urls import user_urlpatterns
from .order.order_urls import order_urlpatterns
from .merchant.merchant_urls import merchant_urlpatterns
from .withdraw.withdraw_urls import withdraw_urlpatterns
from .wallet.wallet_urls import wallet_urlpatterns
from .invite.invite_urls import invite_urlpatterns

urlpatterns = [
    path("health", HealthCheckView.as_view(), name="api-health-check"),

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
    *invite_urlpatterns,

    # 钱包管理
    *wallet_urlpatterns,

    # 提现管理
    *withdraw_urlpatterns,
]
