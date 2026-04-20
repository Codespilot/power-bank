import re
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.generate_snowflake_id import generate_snowflake_id

from .models import Merchant, MerchantHistory, User


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


def _format_agent_display(user):
    if not user:
        return "--"
    display_name = (getattr(user, "fullname", "") or "").strip() or getattr(user, "username", "") or "--"
    phone = (getattr(user, "phone", "") or "").strip()
    return f"{display_name}（{phone}）" if phone else display_name


class MerchantListView(APIView):
    def get(self, request):
        merchant_name = str(request.GET.get("merchant_name", "")).strip()
        agent_keyword = str(request.GET.get("agent_keyword", "")).strip()

        page = _parse_int(request.GET.get("page", 1), 1)
        if page <= 0:
            page = 1

        limit = _parse_int(request.GET.get("limit", 10), 10)
        if limit <= 0:
            limit = 10

        offset = (page - 1) * limit

        where_clauses = []
        params = []

        if merchant_name:
            where_clauses.append("mch.name LIKE %s")
            params.append(f"%{merchant_name}%")

        if agent_keyword:
            if FULL_PHONE_REGEX.fullmatch(agent_keyword):
                where_clauses.append("usr.phone = %s")
                params.append(agent_keyword)
            else:
                where_clauses.append(
                    "(usr.username LIKE %s OR usr.fullname LIKE %s OR usr.phone LIKE %s OR usr.email LIKE %s)"
                )
                fuzzy_value = f"%{agent_keyword}%"
                params.extend([fuzzy_value, fuzzy_value, fuzzy_value, fuzzy_value])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"""
            SELECT COUNT(1)
            FROM merchant AS mch
            LEFT JOIN `user` AS usr ON mch.agent_id = usr.id
            {where_sql}
        """

        data_sql = f"""
            WITH orders AS (
                SELECT
                    merchant_id,
                    COUNT(1) AS order_count,
                    COALESCE(SUM(order_amount), 0) AS order_amount,
                    COALESCE(SUM(merchant_profit), 0) AS merchant_profit
                FROM merchant_order
                GROUP BY merchant_id
            )
            SELECT
                mch.id,
                mch.name,
                usr.fullname AS agent_fullname,
                usr.phone AS agent_phone,
                COALESCE(odr.order_count, 0) AS order_count,
                COALESCE(odr.order_amount, 0) AS order_amount,
                COALESCE(odr.merchant_profit, 0) AS merchant_profit
            FROM merchant AS mch
            LEFT JOIN `user` AS usr ON mch.agent_id = usr.id
            LEFT JOIN orders AS odr ON mch.id = odr.merchant_id
            {where_sql}
            ORDER BY mch.created_at DESC, mch.id DESC
            LIMIT %s OFFSET %s
        """

        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            count = cursor.fetchone()[0]

            cursor.execute(data_sql, params + [limit, offset])
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        results = [
            {
                "id": str(row["id"]),
                "merchant_id": str(row["id"]),
                "merchant_name": row["name"],
                "agent_fullname": (row.get("agent_fullname") or "").strip() or "--",
                "agent_phone": (row.get("agent_phone") or "").strip() or "--",
                "order_count": int(row.get("order_count") or 0),
                "order_amount": _format_decimal(row.get("order_amount")),
                "merchant_profit": _format_decimal(row.get("merchant_profit")),
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


class MerchantHistoryListView(APIView):
    def get(self, request, id):
        merchant = Merchant.objects.filter(id=id).first()
        if not merchant:
            return Response(
                {"count": 0, "results": [], "message": "商户不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        histories = (
            MerchantHistory.objects.filter(merchant_id=id)
            .select_related("merchant", "new_agent", "old_agent")
            .order_by("-created_at", "-id")
        )

        results = [
            {
                "merchant_id": str(history.merchant_id),
                "merchant_name": history.merchant.name,
                "new_agent": _format_agent_display(history.new_agent),
                "old_agent": _format_agent_display(history.old_agent),
                "created_at": history.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for history in histories
        ]

        return Response({"count": len(results), "results": results, "message": "查询成功"})


def _assign_merchants(merchant_ids, agent_phone):
    agent_phone = str(agent_phone or "").strip()
    if not agent_phone:
        return Response({"message": "请输入代理商手机号"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(phone=agent_phone).first()
    if not user:
        return Response({"message": "未找到对应代理商"}, status=status.HTTP_400_BAD_REQUEST)

    normalized_ids = []
    for merchant_id in merchant_ids:
        try:
            normalized_ids.append(int(str(merchant_id).strip()))
        except (TypeError, ValueError, AttributeError):
            continue

    if not normalized_ids:
        return Response({"message": "请选择要划拨的商户"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        merchants = list(
            Merchant.objects.select_for_update().filter(id__in=normalized_ids).order_by("id")
        )
        if not merchants:
            return Response({"message": "商户不存在"}, status=status.HTTP_404_NOT_FOUND)

        for merchant in merchants:
            old_agent_id = merchant.agent_id
            merchant.agent = user
            merchant.save(update_fields=["agent"])
            MerchantHistory.objects.create(
                id=generate_snowflake_id(),
                merchant=merchant,
                old_agent_id=old_agent_id,
                new_agent=user,
                created_at=timezone.now(),
            )

    return Response({"message": "划拨成功"})


class MerchantAssignAgentView(APIView):
    def post(self, request, id):
        return _assign_merchants([id], request.data.get("agent_phone", ""))


class MerchantBatchAssignAgentView(APIView):
    def post(self, request):
        merchant_ids = request.data.get("merchant_ids", [])
        return _assign_merchants(merchant_ids, request.data.get("agent_phone", ""))
