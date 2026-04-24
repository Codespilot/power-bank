from django.urls import path

from .order_views import (
    OrderListView,
    OrderImportDetailView,
    OrderImportListCreateView,
    OrderImportRunProfitView,
    OrderImportRunningCountView,
)

order_urlpatterns = [
    path("orders", OrderListView.as_view(), name="api-orders-list"),
    path("orders/import", OrderImportListCreateView.as_view(), name="api-order-imports-list-create"),
    path("orders/import/<int:id>", OrderImportDetailView.as_view(), name="api-order-imports-detail"),
    path("orders/import/<int:id>/run-profit", OrderImportRunProfitView.as_view(), name="api-order-imports-run-profit"),
    path("orders/import/running-count", OrderImportRunningCountView.as_view(), name="api-order-imports-running-count"),
]
