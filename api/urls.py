from django.urls import path


from .views import HealthCheckView
from .user.user_views import TokenGrantView, TokenRefreshView

from .profile.profile_urls import profile_urlpatterns
from .user.user_urls import user_urlpatterns
from .order.order_urls import order_urlpatterns
from .merchant.merchant_urls import merchant_urlpatterns
from .withdraw.withdraw_urls import withdraw_urlpatterns
from .wallet.wallet_urls import wallet_urlpatterns
from .invite.invite_urls import invite_urlpatterns
from .term.term_urls import term_urlpatterns
from .attachment.attachment_urls import attachment_urlpatterns
from .bankcard.bankcard_urls import bankcard_urlpatterns
from .profit.profit_urls import profit_urlpatterns

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
    *profit_urlpatterns,

    # 邀请码管理
    *invite_urlpatterns,

    # 钱包管理
    *wallet_urlpatterns,

    # 提现管理
    *withdraw_urlpatterns,

    # 协议管理
    *term_urlpatterns,

    # 附件管理
    *attachment_urlpatterns,

    # 银行卡管理
    *bankcard_urlpatterns,
]
