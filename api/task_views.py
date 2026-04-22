from datetime import datetime, time as dt_time, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import get_request_user_id
from .models import ProfitTaskRecord, UserRole


def _parse_int(value, default):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return parsed


def _format_datetime(value):
    if not value:
        return "--"
    if timezone.is_naive(value):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


class ProfitTaskRecordListView(APIView):
    """分润任务运行记录分页查询。"""

    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                {"count": 0, "results": [], "message": "未登录"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        is_admin = UserRole.objects.filter(
            user_id=current_user_id, role=UserRole.ROLE_ADMIN
        ).exists()
        if not is_admin:
            return Response(
                {"count": 0, "results": [], "message": "无权限访问"},
                status=status.HTTP_403_FORBIDDEN,
            )

        from_date = str(request.GET.get("from", "")).strip()
        to_date = str(request.GET.get("to", "")).strip()

        page = _parse_int(request.GET.get("page", 1), 1)
        if page <= 0:
            page = 1

        limit = _parse_int(request.GET.get("limit", 10), 10)
        if limit <= 0:
            limit = 10

        queryset = ProfitTaskRecord.objects.all().order_by("-run_time", "-id")
        try:
            if from_date:
                start_dt = timezone.make_aware(
                    datetime.combine(
                        datetime.strptime(from_date, "%Y-%m-%d").date(), dt_time.min
                    )
                )
                queryset = queryset.filter(run_time__gte=start_dt)

            if to_date:
                end_dt = timezone.make_aware(
                    datetime.combine(
                        datetime.strptime(to_date, "%Y-%m-%d").date(), dt_time.min
                    )
                ) + timedelta(days=1)
                queryset = queryset.filter(run_time__lt=end_dt)
        except ValueError:
            return Response(
                {"count": 0, "results": [], "message": "日期格式错误"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count = queryset.count()
        offset = (page - 1) * limit
        rows = list(queryset[offset : offset + limit])

        results = [
            {
                "id": str(row.id),
                "run_time": _format_datetime(row.run_time),
                "duration_ms": int(row.duration_ms or 0),
                "data_scanned": int(row.data_scanned or 0),
                "profit_data_count": int(row.profit_data_count or 0),
                "error_message": row.error_message or "",
                "created_at": _format_datetime(row.created_at),
            }
            for row in rows
        ]

        return Response(
            {
                "count": count,
                "page": page,
                "limit": limit,
                "results": results,
                "message": "查询成功",
            }
        )
