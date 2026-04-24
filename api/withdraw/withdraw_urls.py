from django.urls import path

from .withdraw_views import WithdrawApproveView, WithdrawCancelView, WithdrawListView, WithdrawRejectView

withdraw_urlpatterns = [
    path("withdraws", WithdrawListView.as_view(), name="api-withdraws"),
    path("withdraws/<int:id>/approve", WithdrawApproveView.as_view(), name="api-withdraws-approve"),
    path("withdraws/<int:id>/reject", WithdrawRejectView.as_view(), name="api-withdraws-reject"),
    path("withdraws/<int:id>/cancel", WithdrawCancelView.as_view(), name="api-withdraws-cancel"),
]
