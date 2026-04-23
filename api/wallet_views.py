from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from api.serializers import GenericResponseSerializer

from .wallet_serializers import (
    WalletInfoSerializer,
    WalletWithdrawRequestSerializer,
    WalletWithdrawResponseSerializer,
    WalletRecordListRequestSerializer,
    WalletRecordListResponseSerializer,
)

from utils.generate_snowflake_id import generate_snowflake_id

from .auth import get_request_user_id
from .models import Wallet, WalletRecord, Withdraw


_AMOUNT_QUANT = Decimal("0.01")


def _quantize_amount(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _format_amount(value) -> str:
    return format(_quantize_amount(value), "f")


def _format_datetime(value) -> str:
    if not value:
        return "--"
    if timezone.is_naive(value):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def _parse_int(value, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError, AttributeError):
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
        "total_amount": _format_amount(wallet.total_amount),
        "frozen_amount": _format_amount(wallet.frozen_amount),
        "pending_amount": _format_amount(wallet.pending_amount),
        "available_amount": _format_amount(wallet.available_amount),
    }


class WalletView(APIView):
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
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        wallet, _ = Wallet.objects.get_or_create(id=user_id, defaults=_wallet_defaults())
        return Response({**_serialize_wallet(wallet), "message": "查询成功"})

    @extend_schema(
        tags=["wallet"],
        summary="申请提现",
        description="提交提现申请，冻结相应金额并生成提现申请单。",
        request=WalletWithdrawRequestSerializer,
        responses={200: WalletWithdrawResponseSerializer, 400: dict, 401: dict},
    )
    def post(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            amount = _quantize_amount(request.data.get("amount", "0"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"message": "提现金额格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        if amount < Decimal("0.01"):
            return Response({"message": "提现金额不能低于0.01"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if Withdraw.objects.select_for_update().filter(
                user_id=user_id,
                status__in=[Withdraw.STATUS_PENDING_SUBMIT, Withdraw.STATUS_PENDING_APPROVAL],
            ).exists():
                return Response({"message": "当前有待处理的提现申请，请稍后再试"}, status=status.HTTP_400_BAD_REQUEST)

            wallet, _ = Wallet.objects.select_for_update().get_or_create(id=user_id, defaults=_wallet_defaults())
            before_amount = _quantize_amount(wallet.available_amount)
            if amount > before_amount:
                return Response({"message": "提现金额不能大于可用金额"}, status=status.HTTP_400_BAD_REQUEST)

            after_amount = _quantize_amount(before_amount - amount)
            wallet.available_amount = after_amount
            wallet.frozen_amount = _quantize_amount(wallet.frozen_amount + amount)
            wallet.save(update_fields=["available_amount", "frozen_amount"])

            remark = str(request.data.get("remark", "")).strip() or "提现申请，资金冻结"
            withdraw = Withdraw.objects.create(
                id=generate_snowflake_id(),
                user_id=user_id,
                amount=amount,
                remark=remark,
                status=Withdraw.STATUS_PENDING_APPROVAL,
                created_at=timezone.now(),
            )

            # 提交申请时仅冻结余额并生成申请单，不立即写入钱包流水；
            # 后续审核通过/拒绝时再记录最终资金变动。

        refreshed_wallet = Wallet.objects.get(id=user_id)
        return Response(
            {
                **_serialize_wallet(refreshed_wallet),
                "withdraw_id": str(withdraw.id),
                "message": "提现申请已提交",
            }
        )


class WalletRecordListView(APIView):
    """钱包流水查询接口，支持按日期区间过滤。"""

    @extend_schema(
        tags=["wallet"],
        summary="获取钱包流水记录",
        description="分页查询当前用户的钱包流水记录，支持按日期区间过滤。",
        parameters=[
            OpenApiParameter(name="page", description="页码，默认1", required=False, type=int),
            OpenApiParameter(name="limit", description="每页数量，默认10", required=False, type=int),
            OpenApiParameter(name="from", description="起始日期 (YYYY-MM-DD)", required=False, type=str),
            OpenApiParameter(name="to", description="结束日期 (YYYY-MM-DD)", required=False, type=str),
        ],
        responses={200: GenericResponseSerializer[WalletRecordListResponseSerializer], 400: dict, 401: dict},
    )
    def get(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"count": 0, "results": [], "message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        qs = WalletRecord.objects.filter(user_id=user_id).order_by("-created_at", "-id")

        date_from = str(request.GET.get("from", "")).strip()
        date_to = str(request.GET.get("to", "")).strip()
        try:
            if date_from:
                start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_from, "%Y-%m-%d").date(), dt_time.min))
                qs = qs.filter(created_at__gte=start_dt)
            if date_to:
                end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_to, "%Y-%m-%d").date(), dt_time.min)) + timedelta(days=1)
                qs = qs.filter(created_at__lt=end_dt)
        except ValueError:
            return Response({"count": 0, "results": [], "message": "日期格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        page = _parse_int(request.GET.get("page", 1), 1)
        limit = _parse_int(request.GET.get("limit", 10), 10)
        offset = (page - 1) * limit

        count = qs.count()
        records = qs[offset: offset + limit]
        results = [
            {
                "id": str(item.id),
                "amount": _format_amount(item.amount),
                "before_amount": _format_amount(item.before_amount),
                "after_amount": _format_amount(item.after_amount),
                "remark": item.remark or "--",
                "created_at": _format_datetime(item.created_at),
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
