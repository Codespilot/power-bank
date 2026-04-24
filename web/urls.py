from django.urls import path

from .views import CaptchaImageView, HomePageView, LoginPageView, RegisterPageView, LogoutView, UserListPageView, AgentListPageView, MerchantListPageView, MerchantHistoryPageView, ProfitListPageView, TaskRecordListPageView, ProfilePageView, InvitePageView, WalletPageView, WithdrawPageView, OrderListPageView, OrderImportListPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("login/captcha/", CaptchaImageView.as_view(), name="login-captcha"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("user/", UserListPageView.as_view(), name="user-list"),
    path("agent/", AgentListPageView.as_view(), name="agent-list"),
    path("merchant/", MerchantListPageView.as_view(), name="merchant-list"),
    path("merchant/history/", MerchantHistoryPageView.as_view(), name="merchant-history-list"),
    path("profit/", ProfitListPageView.as_view(), name="profit-list"),
    path("task/", TaskRecordListPageView.as_view(), name="task-record-list"),
    path("profile/", ProfilePageView.as_view(), name="profile-page"),
    path("invite/", InvitePageView.as_view(), name="invite-page"),
    path("wallet/", WalletPageView.as_view(), name="wallet-page"),
    path("withdraw/", WithdrawPageView.as_view(), name="withdraw-page"),
    path("order/", OrderListPageView.as_view(), name="order-list"),
    path("order/import/", OrderImportListPageView.as_view(), name="order-import-list"),
]
