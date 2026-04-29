from django.urls import path

from .term_views import (
    TermListView,
    TermDetailView,
    TermEnableDisableView,
    TermPublishView,
    TermPrivacyView,
    TermUserAgreementView,
)

term_urlpatterns = [
    # 管理接口
    path("terms", TermListView.as_view(), name="api-terms-list"),
    path("terms/<int:id>", TermDetailView.as_view(), name="api-terms-detail"),
    path("terms/<int:id>/enable", TermEnableDisableView.as_view(), {"action": "enable"}, name="api-terms-enable"),
    path("terms/<int:id>/disable", TermEnableDisableView.as_view(), {"action": "disable"}, name="api-terms-disable"),
    path("terms/<int:id>/publish", TermPublishView.as_view(), name="api-terms-publish"),

    # 公开接口
    path("terms/privacy", TermPrivacyView.as_view(), name="api-terms-privacy"),
    path("terms/userterm", TermUserAgreementView.as_view(), name="api-terms-userterm"),
]
