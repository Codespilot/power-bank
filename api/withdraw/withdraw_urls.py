from django.urls import path

from .withdraw_views import (
    WithdrawApproveView,
    WithdrawCancelView,
    WithdrawListView,
    WithdrawRejectView,
    WithdrawCreateView,
)


def get_view(request):
    match request.method:
        case "POST":
            return WithdrawCreateView.as_view()(request)
        case "GET":
            return WithdrawListView.as_view()(request)
        case _:
            return None


withdraw_urlpatterns = [
    path("withdraws", get_view, name="api-withdraws"),
    path(
        "withdraws/<int:id>/approve",
        WithdrawApproveView.as_view(),
        name="api-withdraws-approve",
    ),
    path(
        "withdraws/<int:id>/reject",
        WithdrawRejectView.as_view(),
        name="api-withdraws-reject",
    ),
    path(
        "withdraws/<int:id>/cancel",
        WithdrawCancelView.as_view(),
        name="api-withdraws-cancel",
    ),
]
