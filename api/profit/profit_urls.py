from django.urls import path

from .profit_views import ProfitListView, ProfitTaskListView

profit_urlpatterns = [
    path("profits", ProfitListView.as_view(), name="api-profits-list"),
    path("profit-tasks", ProfitTaskListView.as_view(), name="api-profit-tasks-list"),
]
