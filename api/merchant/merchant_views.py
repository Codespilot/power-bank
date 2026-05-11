from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema
from .merchant_serializers import (
    MerchantListResponseSerializer,
    MerchantHistoryResponseSerializer,
    MerchantAssignAgentRequestSerializer,
    MerchantBatchAssignAgentRequestSerializer,
)

from utils.generate_snowflake_id import generate_snowflake_id
from ..serializers import CommonResponseSerializer, GenericResponseSerializer
from ..auth import get_current_user, get_request_user_id
from ..models import Merchant, MerchantHistory, User
from api.regex import MOBILE_REGEX


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
    display_name = (
        (getattr(user, "fullname", "") or "").strip()
        or getattr(user, "username", "")
        or "--"
    )
    phone = (getattr(user, "phone", "") or "").strip()
    return f"{display_name}（{phone}）" if phone else display_name


class MerchantListView(APIView):
    @extend_schema(
        tags=["merchants"],
        summary="获取商户列表",
        description="分页查询商户列表，支持按商户名称和代理商关键字筛选。管理员可见所有商户，普通代理商仅可见自己名下的商户。",
        parameters=[
            OpenApiParameter(
                name="merchant", description="商户名称关键字", required=False, type=str
            ),
            OpenApiParameter(
                name="agent",
                description="代理商关键字（手机号/姓名/用户名/邮箱）",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="page", description="页码，默认1", required=False, type=int
            ),
            OpenApiParameter(
                name="limit", description="每页数量，默认10", required=False, type=int
            ),
        ],
        responses={
            200: GenericResponseSerializer[MerchantListResponseSerializer],
            401: CommonResponseSerializer,
        },
    )
    def get(self, request):
        current_user_id, is_admin = get_current_user(request)
        if not current_user_id:
            return Response(
                {"count": 0, "results": [], "message": "未登录"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        merchant = str(request.GET.get("merchant", "")).strip()
        agent = str(request.GET.get("agent", "")).strip()

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
            where_clauses.append("mch.agent_id = %s")
            params.append(int(current_user_id))

        if merchant:
            where_clauses.append("mch.name LIKE %s")
            params.append(f"%{merchant}%")

        if agent:
            if MOBILE_REGEX.fullmatch(agent):
                where_clauses.append("usr.phone = %s")
                params.append(agent)
            else:
                where_clauses.append(
                    "(usr.username LIKE %s OR usr.fullname LIKE %s OR usr.phone LIKE %s OR usr.email LIKE %s)"
                )
                fuzzy_value = f"%{agent}%"
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
                FROM `order`
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
    @extend_schema(
        tags=["merchants"],
        summary="获取商户划拨历史",
        description="查询指定商户的所有划拨历史记录，包括原代理商和新代理商信息。",
        parameters=[
            OpenApiParameter(
                name="id",
                description="商户ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses={
            200: GenericResponseSerializer[MerchantHistoryResponseSerializer],
            404: CommonResponseSerializer,
        },
    )
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
                "new_agent_id": history.new_agent_id,
                "new_agent_fullname": (
                    history.new_agent.fullname if history.new_agent else "--"
                ),
                "new_agent_phone": (
                    history.new_agent.phone if history.new_agent else "--"
                ),
                "old_agent_id": history.old_agent_id,
                "old_agent_fullname": (
                    history.old_agent.fullname if history.old_agent else "--"
                ),
                "old_agent_phone": (
                    history.old_agent.phone if history.old_agent else "--"
                ),
                "new_agent": _format_agent_display(history.new_agent),
                "old_agent": _format_agent_display(history.old_agent),
                "created_at": history.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for history in histories
        ]

        return Response(
            {"count": len(results), "results": results, "message": "查询成功"}
        )


def _assign_merchants(request, merchant_ids, agent_phone: str = None, agent_id: int = None):
    """
    将一个或多个商户划拨给指定代理商。管理员可划拨任意商户，普通代理商仅能划拨自己名下的商户给自己的直属下级代理商。

    args:
        request: 当前请求对象
        merchant_ids: 商户ID列表
        agent_phone: 目标代理商手机号（可选）
        agent_id: 目标代理商用户ID（可选）
    returns:
        Response对象，包含操作结果信息
    raises:
        PermissionError: 当普通代理商试图划拨不属于自己的商户或划拨给非直属下级代理商时
        ValueError: 当输入参数无效或缺失时
    """
    current_user_id, is_admin = get_current_user(request)
    if not current_user_id:
        return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

    try:

        user = None
        if agent_id:
            user = User.objects.filter(id=agent_id).first()
        elif agent_phone:
            if not MOBILE_REGEX.fullmatch(agent_phone):
                raise ValueError("代理商手机号格式不正确")
            user = User.objects.filter(phone=agent_phone).first()
        else:
            raise ValueError("参数错误")

        if not user:
            raise ValueError("未找到对应代理商")

        if not is_admin and int(user.agent_id or 0) != int(current_user_id):
            raise PermissionError("普通用户仅能划拨给自己的直属下级代理商")

        normalized_ids = []
        for merchant_id in merchant_ids:
            try:
                normalized_ids.append(int(str(merchant_id).strip()))
            except (TypeError, ValueError, AttributeError):
                continue

        if not normalized_ids:
            raise ValueError("请选择要划拨的商户")

        with transaction.atomic():
            merchants = list(
                Merchant.objects.select_for_update()
                .filter(id__in=normalized_ids)
                .order_by("id")
            )
            if not merchants:
                raise ValueError("商户不存在")

            if not is_admin:
                invalid_merchants = [
                    str(merchant.id)
                    for merchant in merchants
                    if int(merchant.agent_id or 0) != int(current_user_id)
                ]
                if invalid_merchants:
                    raise PermissionError("普通用户仅能划拨自己名下的商户")

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
    except PermissionError as error:
        return Response({"message": str(error)}, status=status.HTTP_403_FORBIDDEN)
    except (TypeError, ValueError) as error:
        return Response({"message": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"message": f"划拨失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
        )


class MerchantAssignAgentView(APIView):
    @extend_schema(
        tags=["merchants"],
        operation_id="merchant_allocate_detail",
        summary="划拨单个商户",
        description="将单个商户划拨给指定代理商。管理员可划拨任意商户，普通代理商仅能划拨自己名下的商户给自己的直属下级代理商。",
        parameters=[
            OpenApiParameter(
                name="id",
                description="商户ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ],
        request=MerchantAssignAgentRequestSerializer,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer,
            401: CommonResponseSerializer,
            404: CommonResponseSerializer,
        },
    )
    def post(self, request, id):
        return _assign_merchants(
            request,
            [id],
            request.data.get("agent_phone", ""),
            agent_id=int(request.data.get("agent_id")) if request.data.get("agent_id") else None,
        )


class MerchantBatchAssignAgentView(APIView):
    @extend_schema(
        tags=["merchants"],
        operation_id="merchant_allocate_bulk",
        summary="批量划拨商户",
        description="将多个商户批量划拨给指定代理商。管理员可划拨任意商户，普通代理商仅能划拨自己名下的商户给自己的直属下级代理商。",
        request=MerchantBatchAssignAgentRequestSerializer,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer,
            401: CommonResponseSerializer,
            404: CommonResponseSerializer,
        },
    )
    def post(self, request):
        merchant_ids = request.data.get("merchant_ids", [])
        return _assign_merchants(
            request,
            merchant_ids,
            request.data.get("agent_phone", ""),
            agent_id=int(request.data.get("agent_id")) if request.data.get("agent_id") else None,
        )


class MerchantHistoryInView(APIView):
    @extend_schema(
        tags=["merchants"],
        operation_id="merchant_history_in",
        summary="查询划入记录",
        description="查询划拨到当前代理商名下的商户历史记录。",
        parameters=[
            OpenApiParameter(
                name="keyword",
                description="搜索关键字（商户名称/代理商姓名/手机号/用户名）",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="page", description="页码，默认1", required=False, type=int
            ),
            OpenApiParameter(
                name="limit", description="每页数量，默认10", required=False, type=int
            ),
        ],
        responses={
            200: GenericResponseSerializer[MerchantHistoryResponseSerializer],
            401: CommonResponseSerializer,
        },
    )
    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                {
                    "count": 0,
                    "page": 1,
                    "limit": 10,
                    "results": [],
                    "message": "未登录",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        keyword = str(request.GET.get("keyword", "")).strip()

        base_qs = MerchantHistory.objects.filter(
            new_agent_id=current_user_id
        ).select_related("merchant", "new_agent", "old_agent")

        if keyword:
            base_qs = base_qs.filter(
                Q(merchant__name__icontains=keyword)
                | Q(old_agent__fullname__icontains=keyword)
                | Q(old_agent__phone__icontains=keyword)
                | Q(old_agent__username__icontains=keyword)
            )

        return _paginate_history(request, base_qs)


class MerchantHistoryOutView(APIView):
    @extend_schema(
        tags=["merchants"],
        operation_id="merchant_history_out",
        summary="查询划出记录",
        description="查询从当前代理商划出的商户历史记录。",
        parameters=[
            OpenApiParameter(
                name="keyword",
                description="搜索关键字（商户名称/代理商姓名/手机号/用户名）",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="page", description="页码，默认1", required=False, type=int
            ),
            OpenApiParameter(
                name="limit", description="每页数量，默认10", required=False, type=int
            ),
        ],
        responses={
            200: GenericResponseSerializer[MerchantHistoryResponseSerializer],
            401: CommonResponseSerializer,
        },
    )
    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                {
                    "count": 0,
                    "page": 1,
                    "limit": 10,
                    "results": [],
                    "message": "未登录",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        keyword = str(request.GET.get("keyword", "")).strip()

        base_qs = MerchantHistory.objects.filter(
            old_agent_id=current_user_id
        ).select_related("merchant", "new_agent", "old_agent")

        if keyword:
            base_qs = base_qs.filter(
                Q(merchant__name__icontains=keyword)
                | Q(new_agent__fullname__icontains=keyword)
                | Q(new_agent__phone__icontains=keyword)
                | Q(new_agent__username__icontains=keyword)
            )

        return _paginate_history(request, base_qs)


def _paginate_history(request, base_qs):
    page = _parse_int(request.GET.get("page", 1), 1)
    if page <= 0:
        page = 1
    limit = _parse_int(request.GET.get("limit", 10), 10)
    if limit <= 0:
        limit = 10
    offset = (page - 1) * limit

    count = base_qs.count()
    histories = base_qs.order_by("-created_at", "-id")[offset : offset + limit]

    results = [
        {
            "merchant_id": str(h.merchant_id),
            "merchant_name": h.merchant.name if h.merchant else "--",
            "new_agent_id": h.new_agent_id,
            "new_agent_fullname": h.new_agent.fullname if h.new_agent else "--",
            "new_agent_phone": h.new_agent.phone if h.new_agent else "--",
            "new_agent": _format_agent_display(h.new_agent),
            "old_agent_id": h.old_agent_id,
            "old_agent_fullname": h.old_agent.fullname if h.old_agent else "--",
            "old_agent_phone": h.old_agent.phone if h.old_agent else "--",
            "old_agent": _format_agent_display(h.old_agent),
            "created_at": h.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for h in histories
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
