import re
from datetime import date, datetime, time as dt_time, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import get_request_user_id
from .models import ProfitTaskRecord, User, UserRole
from .profit_tasks import run_profit_allocation_with_tracking


FULL_PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


def _parse_int(value, default):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return parsed


def _format_decimal(value):
    amount = Decimal(str(value or 0))
    return format(amount.quantize(Decimal("0.01")), "f")


def _user_display(fullname, username, phone):
    display_name = (fullname or "").strip() or (username or "").strip() or "--"
    phone = (phone or "").strip()
    return f"{display_name}（{phone}）" if phone else display_name


def _source_display(fullname, username, phone, rate):
    if not fullname and not username and not phone:
        return "--"

    base = _user_display(fullname, username, phone)
    if rate is None:
        return base

    percent = Decimal(str(rate or 0)) * Decimal("100")
    percent_text = format(percent.quantize(Decimal("0.01")), "f")
    return f"{base} {percent_text}%"


def _format_datetime(value):
    if not value:
        return "--"
    if timezone.is_naive(value):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def _to_utc_string(value):
    return value.astimezone(dt_timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


class ProfitListView(APIView):
    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response({"count": 0, "results": [], "message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        current_user = User.objects.filter(id=current_user_id).first()
        if not current_user:
            return Response({"count": 0, "results": [], "message": "用户不存在"}, status=status.HTTP_401_UNAUTHORIZED)

        is_admin = UserRole.objects.filter(user_id=current_user_id, role=UserRole.ROLE_ADMIN).exists()

        keyword = str(request.GET.get("keyword", "")).strip()
        date_start = str(request.GET.get("date_start", "")).strip()
        date_end = str(request.GET.get("date_end", "")).strip()

        page = _parse_int(request.GET.get("page", 1), 1)
        if page <= 0:
            page = 1

        limit = _parse_int(request.GET.get("limit", 10), 10)
        if limit <= 0:
            limit = 10

        offset = (page - 1) * limit

        where_clauses = []
        params = []

        if not is_admin:
            where_clauses.append("pa.user_id = %s")
            params.append(int(current_user_id))

        if keyword:
            if FULL_PHONE_REGEX.fullmatch(keyword):
                where_clauses.append("usr.phone = %s")
                params.append(keyword)
            else:
                fuzzy = f"%{keyword}%"
                where_clauses.append(
                    "(usr.username LIKE %s OR usr.fullname LIKE %s OR usr.phone LIKE %s OR usr.email LIKE %s)"
                )
                params.extend([fuzzy, fuzzy, fuzzy, fuzzy])

        try:
            if date_start:
                start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, "%Y-%m-%d").date(), dt_time.min))
                where_clauses.append("pa.settle_date >= %s")
                params.append(_to_utc_string(start_dt))
            if date_end:
                end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, "%Y-%m-%d").date(), dt_time.min)) + timedelta(days=1)
                where_clauses.append("pa.settle_date < %s")
                params.append(_to_utc_string(end_dt))
        except ValueError:
            return Response({"count": 0, "results": [], "message": "日期格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"""
            SELECT COUNT(1)
            FROM profit_allocation AS pa
            INNER JOIN `user` AS usr ON pa.user_id = usr.id
            {where_sql}
        """

        data_sql = f"""
            SELECT
                pa.id,
                pa.order_import_id,
                pa.settle_date,
                pa.order_amount,
                pa.profit_amount,
                pa.settle_amount,
                pa.settle_source,
                pa.rate,
                pa.created_at,
                usr.username AS agent_username,
                usr.fullname AS agent_fullname,
                usr.phone AS agent_phone,
                src.username AS source_username,
                src.fullname AS source_fullname,
                src.phone AS source_phone
            FROM profit_allocation AS pa
            INNER JOIN `user` AS usr ON pa.user_id = usr.id
            LEFT JOIN `user` AS src ON pa.settle_source_user_id = src.id
            {where_sql}
            ORDER BY pa.settle_date DESC, pa.created_at DESC, pa.id DESC
            LIMIT %s OFFSET %s
        """

        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            count = cursor.fetchone()[0]

            cursor.execute(data_sql, params + [limit, offset])
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        results = []
        for row in rows:
            settle_source = row.get("settle_source") or ""
            results.append(
                {
                    "id": str(row["id"]),
                    "order_import_id": str(row.get("order_import_id") or ""),
                    "settle_date": _format_datetime(row.get("settle_date")),
                    "agent_display": _user_display(row.get("agent_fullname"), row.get("agent_username"), row.get("agent_phone")),
                    "order_amount": _format_decimal(row.get("order_amount")),
                    "profit_amount": _format_decimal(row.get("profit_amount")),
                    "settle_amount": _format_decimal(row.get("settle_amount")),
                    "settle_source": settle_source,
                    "settle_source_text": "直接分润" if settle_source == "direct" else "下级代理商" if settle_source == "subagent" else "--",
                    "source_agent_display": _source_display(
                        row.get("source_fullname"),
                        row.get("source_username"),
                        row.get("source_phone"),
                        row.get("rate"),
                    ),
                    "created_at": _format_datetime(row.get("created_at")),
                }
            )

        return Response(
            {
                "count": count,
                "page": page,
                "limit": limit,
                "results": results,
                "message": "查询成功",
            }
        )


class ProfitTaskListView(APIView):
    """分润任务运行记录分页查询。"""

    def _check_admin(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return None, Response(
                {"count": 0, "results": [], "message": "未登录"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        is_admin = UserRole.objects.filter(
            user_id=current_user_id, role=UserRole.ROLE_ADMIN
        ).exists()
        if not is_admin:
            return None, Response(
                {"count": 0, "results": [], "message": "无权限访问"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return current_user_id, None

    def get(self, request):
        _, error_response = self._check_admin(request)
        if error_response is not None:
            return error_response

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
                "duration": int(row.duration or 0),
                "bill_date": row.bill_date or "",
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

    def post(self, request):
        _, error_response = self._check_admin(request)
        if error_response is not None:
            return error_response

        order_import_id = request.data.get("order_import_id")
        if order_import_id in (None, ""):
            return Response(
                {"message": "请传入 order_import_id，在导入记录页面执行分润"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order_import_id = int(order_import_id)
        except (TypeError, ValueError):
            return Response(
                {"message": "order_import_id 格式错误"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = run_profit_allocation_with_tracking(order_import_id=order_import_id)
        latest_record = ProfitTaskRecord.objects.order_by("-created_at", "-id").first()

        return Response(
            {
                "message": "任务执行完成",
                "result": result,
                "record_id": str(latest_record.id) if latest_record else "",
            }
        )
