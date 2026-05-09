from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from api.exceptions import CredentialError
from api.serializers import GenericResponseSerializer
from ..views import BaseAPIView, handle_request

from .wallet_serializers import (
    WalletInfoSerializer,
    WalletRecordListRequestSerializer,
    WalletRecordListResponseSerializer,
)

from ..models import Wallet, WalletRecord


def _parse_int(value, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except TypeError, ValueError, AttributeError:
        return default


def _wallet_defaults() -> dict:
    return {
        "total_amount": Decimal("0.00"),
        "frozen_amount": Decimal("0.00"),
        "pending_amount": Decimal("0.00"),
        "available_amount": Decimal("0.00"),
    }


def _serialize_wallet(wallet: Wallet) -> dict:
    return {
        "total_amount": BaseAPIView.format_amount(wallet.total_amount),
        "frozen_amount": BaseAPIView.format_amount(wallet.frozen_amount),
        "pending_amount": BaseAPIView.format_amount(wallet.pending_amount),
        "available_amount": BaseAPIView.format_amount(wallet.available_amount),
    }


class WalletView(BaseAPIView):
    """钱包概览与提现申请接口。"""

    @extend_schema(
        tags=["wallet"],
        summary="获取钱包信息",
        description="查询当前用户的钱包概览信息，包括总金额、冻结金额、待结算金额和可用金额。",
        responses={200: WalletInfoSerializer, 401: dict},
    )
    def get(self, request):
        """
        查询钱包信息
        :param request: 请求信息
        :return: 钱包信息字典
        """

        def _handle():
            user_id = self.get_current_user_id(request)
            if not user_id:
                raise CredentialError("未登录")

            wallet, _ = Wallet.objects.get_or_create(
                id=user_id, defaults=_wallet_defaults()
            )
            return Response({**_serialize_wallet(wallet), "message": "查询成功"})

        return handle_request(_handle)


class WalletRecordListView(BaseAPIView):
    """钱包流水查询接口，支持按日期区间过滤。"""

    @extend_schema(
        tags=["wallet"],
        summary="获取钱包流水记录",
        description="分页查询当前用户的钱包流水记录，支持按日期区间过滤。",
        parameters=[
            OpenApiParameter(
                name="page", description="页码，默认1", required=False, type=int
            ),
            OpenApiParameter(
                name="limit", description="每页数量，默认10", required=False, type=int
            ),
            OpenApiParameter(
                name="from",
                description="起始日期 (YYYY-MM-DD)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="to", description="结束日期 (YYYY-MM-DD)", required=False, type=str
            ),
            OpenApiParameter(
                name="type", description="流水类型（income、i、1: 收入, outgo、o、-1: 支出）", required=False, type=str
            ),
        ],
        responses={
            200: GenericResponseSerializer[WalletRecordListResponseSerializer],
            400: dict,
            401: dict,
        },
    )
    def get(self, request):
        def _handle():
            user_id = self.get_current_user_id(request)
            if not user_id:
                return Response(
                    {"count": 0, "results": [], "message": "未登录"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            qs = WalletRecord.objects.filter(user_id=user_id).order_by(
                "-created_at", "-id"
            )

            date_from = str(request.GET.get("from", "")).strip()
            date_to = str(request.GET.get("to", "")).strip()
            type_str = request.GET.get("type").strip().lower() if request.GET.get("type") else None
            match type_str:
                case None | "":
                    pass
                case "i" | "1" | "income":
                    qs = qs.filter(amount__gt=0)
                case "-1" | "o" | "outgo":
                    qs = qs.filter(amount__lt=0)
                case _:
                    return Response(
                        {"count": 0, "results": [], "message": "无效的type参数"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                if date_from:
                    start_dt = timezone.make_aware(
                        datetime.combine(
                            datetime.strptime(date_from, "%Y-%m-%d").date(), dt_time.min
                        )
                    )
                    qs = qs.filter(created_at__gte=start_dt)
                if date_to:
                    end_dt = timezone.make_aware(
                        datetime.combine(
                            datetime.strptime(date_to, "%Y-%m-%d").date(), dt_time.min
                        )
                    ) + timedelta(days=1)
                    qs = qs.filter(created_at__lt=end_dt)
            except ValueError:
                return Response(
                    {"count": 0, "results": [], "message": "日期格式错误"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            page = _parse_int(request.GET.get("page", 1), 1)
            limit = _parse_int(request.GET.get("limit", 10), 10)
            offset = (page - 1) * limit

            count = qs.count()
            records = qs[offset : offset + limit]
            results = [
                {
                    "id": str(item.id),
                    "amount": self.format_amount(item.amount),
                    "before_amount": self.format_amount(item.before_amount),
                    "after_amount": self.format_amount(item.after_amount),
                    "remark": item.remark or "--",
                    "created_at": self.format_datetime(item.created_at),
                    "type": "income" if item.amount > 0 else "outgo",
                    "is_valid": item.is_valid,
                    "outer_type": item.outer_type,
                    "outer_id": str(item.outer_id) if item.outer_id else None,
                    "is_valid_text": "有效" if item.is_valid else "无效",
                }
                for item in records
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

        return handle_request(_handle)
