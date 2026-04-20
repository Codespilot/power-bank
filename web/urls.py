from django.urls import path

from .views import CaptchaImageView, HomePageView, LoginPageView, LogoutView, UserListPageView, MerchantListPageView, MerchantHistoryPageView, ProfitListPageView, ProfilePageView, OrderListPageView, OrderImportListPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("login", LoginPageView.as_view(), name="login"),
    path("login/captcha/", CaptchaImageView.as_view(), name="login-captcha"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("logout/", LogoutView.as_view()),
    path("user/", UserListPageView.as_view(), name="user-list"),
    path("merchant/", MerchantListPageView.as_view(), name="merchant-list"),
    path("merchant/history/", MerchantHistoryPageView.as_view(), name="merchant-history-list"),
    path("profit/", ProfitListPageView.as_view(), name="profit-list"),
    path("profile/", ProfilePageView.as_view(), name="profile-page"),
    path("order/", OrderListPageView.as_view(), name="order-list"),
    path("order/import/", OrderImportListPageView.as_view(), name="order-import-list"),
]
