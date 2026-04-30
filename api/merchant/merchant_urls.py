from django.urls import path

from .merchant_views import (
    MerchantAssignAgentView,
    MerchantBatchAssignAgentView,
    MerchantHistoryInView,
    MerchantHistoryListView,
    MerchantHistoryOutView,
    MerchantListView,
)

merchant_urlpatterns = [
    path("merchants", MerchantListView.as_view(), name="api-merchants-list"),
    path(
        "merchants/allocate",
        MerchantBatchAssignAgentView.as_view(),
        name="api-merchants-batch-assign-agent",
    ),
    path(
        "merchants/history/in",
        MerchantHistoryInView.as_view(),
        name="api-merchants-history-in",
    ),
    path(
        "merchants/history/out",
        MerchantHistoryOutView.as_view(),
        name="api-merchants-history-out",
    ),
    path(
        "merchants/<int:id>/history",
        MerchantHistoryListView.as_view(),
        name="api-merchants-history",
    ),
    path(
        "merchants/<int:id>/allocate",
        MerchantAssignAgentView.as_view(),
        name="api-merchants-assign-agent",
    ),
]
