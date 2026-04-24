from django.urls import path

from .wallet_views import WalletRecordListView, WalletView

wallet_urlpatterns = [
    path("wallet", WalletView.as_view(), name="api-wallet"),
    path("wallet/record", WalletRecordListView.as_view(), name="api-wallet-record"),
]
