from django.urls import path

from .bankcard_views import (
    BankCardListView,
    BankCardDetailView,
    BankCardLookupView,
)

bankcard_urlpatterns = [
    path("bankcards", BankCardListView.as_view(), name="api-bankcards-list"),
    path("bankcards/lookup", BankCardLookupView.as_view(), name="api-bankcards-lookup"),
    path("bankcards/<int:id>", BankCardDetailView.as_view(), name="api-bankcards-detail"),
]
