from django.urls import path, re_path

from .views import CaptchaImageView, HomePageView, LoginPageView, RegisterPageView, LogoutView, UserListPageView, AgentListPageView, MerchantListPageView, MerchantHistoryPageView, ProfitListPageView, TaskRecordListPageView, ProfilePageView, InvitePageView, WalletPageView, WithdrawPageView, OrderListPageView, OrderImportListPageView, TermListPageView, TermFormPageView, AttachmentListPageView, BankCardListPageView, BankCardFormPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("login", LoginPageView.as_view(), name="login"),
    path("register", RegisterPageView.as_view(), name="register"),
    path("captcha", CaptchaImageView.as_view(), name="login-captcha"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("user", UserListPageView.as_view(), name="user-list"),
    path("agent", AgentListPageView.as_view(), name="agent-list"),
    path("merchant", MerchantListPageView.as_view(), name="merchant-list"),
    path("merchant/history", MerchantHistoryPageView.as_view(), name="merchant-history-list"),
    path("profit", ProfitListPageView.as_view(), name="profit-list"),
    path("task", TaskRecordListPageView.as_view(), name="task-record-list"),
    path("profile", ProfilePageView.as_view(), name="profile-page"),
    path("invite", InvitePageView.as_view(), name="invite-page"),
    path("wallet", WalletPageView.as_view(), name="wallet-page"),
    path("withdraw", WithdrawPageView.as_view(), name="withdraw-page"),
    path("order", OrderListPageView.as_view(), name="order-list"),
    path("order/import", OrderImportListPageView.as_view(), name="order-import-list"),
    path("term", TermListPageView.as_view(), name="term-list"),
    path("term/add", TermFormPageView.as_view(), name="term-add"),
    re_path(r"^term/edit/(?P<id>\d+)$", TermFormPageView.as_view(), name="term-edit"),
    path("attachment", AttachmentListPageView.as_view(), name="attachment-list"),
    path("bankcard", BankCardListPageView.as_view(), name="bankcard-list"),
    path("bankcard/add", BankCardFormPageView.as_view(), name="bankcard-add"),
    re_path(r"^bankcard/edit/(?P<id>\d+)$", BankCardFormPageView.as_view(), name="bankcard-edit"),
]
