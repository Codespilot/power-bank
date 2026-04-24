from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.generate_snowflake_id import generate_snowflake_id

from .auth import get_request_user_id
from .models import User, UserRole, Wallet, WalletRecord, Withdraw
from .serializers import GenericResponseSerializer
from .withdraw_serializers import WithdrawListResponseSerializer

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


def _display_user(user: User | None) -> str:
    if not user:
        return "--"
    name = (user.fullname or "").strip() or (user.username or "").strip() or "--"
    phone = (user.phone or "").strip()
    return f"{name}（{phone}）" if phone else name


def _is_admin(user_id: int) -> bool:
    return UserRole.objects.filter(user_id=user_id, role=UserRole.ROLE_ADMIN).exists()


class WithdrawListView(APIView):
    """提现申请列表接口。"""

    @extend_schema(
        summary="提现申请列表",
        tags=["wallet"],
        parameters=[
            OpenApiParameter(name="keyword", description="搜索关键词，匹配用户名、姓名、手机号、邮箱", required=False),
            OpenApiParameter(name="status", description="申请状态，0=待审批，1=已批准，2=已驳回，3=已作废", required=False),
            OpenApiParameter(name="date_start", description="申请开始日期，格式YYYY-MM-DD", required=False),
            OpenApiParameter(name="date_end", description="申请结束日期，格式YYYY-MM-DD", required=False),
            OpenApiParameter(name="page", description="页码，默认为1", required=False),
            OpenApiParameter(name="limit", description="每页数量，默认为10", required=False),
        ],
        responses={
            200: GenericResponseSerializer[WithdrawListResponseSerializer]}
    )
    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response({"count": 0, "results": [], "message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        is_admin = _is_admin(current_user_id)
        qs = Withdraw.objects.select_related("user", "audit_user").order_by("-created_at", "-id")

        if not is_admin:
            qs = qs.filter(user_id=current_user_id)

        keyword = str(request.GET.get("keyword", "")).strip()
        date_start = str(request.GET.get("date_start", "")).strip()
        date_end = str(request.GET.get("date_end", "")).strip()
        status_value = str(request.GET.get("status", "")).strip()

        if keyword:
            qs = qs.filter(
                Q(user__username__icontains=keyword)
                | Q(user__fullname__icontains=keyword)
                | Q(user__phone__icontains=keyword)
                | Q(user__email__icontains=keyword)
            )

        if status_value.isdigit():
            qs = qs.filter(status=int(status_value))

        try:
            if date_start:
                start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, "%Y-%m-%d").date(), dt_time.min))
                qs = qs.filter(created_at__gte=start_dt)
            if date_end:
                end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, "%Y-%m-%d").date(), dt_time.min)) + timedelta(days=1)
                qs = qs.filter(created_at__lt=end_dt)
        except ValueError:
            return Response({"count": 0, "results": [], "message": "日期格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        page = int(request.GET.get("page", 1) or 1)
        limit = int(request.GET.get("limit", 10) or 10)
        if page <= 0:
            page = 1
        if limit <= 0:
            limit = 10
        offset = (page - 1) * limit

        count = qs.count()
        page_rows = list(qs[offset: offset + limit])
        wallets = Wallet.objects.in_bulk([row.user_id for row in page_rows])

        results = []
        for row in page_rows:
            wallet = wallets.get(row.user_id)
            results.append(
                {
                    "id": str(row.id),
                    "created_at": _format_datetime(row.created_at),
                    "applicant_display": _display_user(row.user),
                    "amount": _format_amount(row.amount),
                    "available_amount": _format_amount(wallet.available_amount if wallet else 0),
                    "frozen_amount": _format_amount(wallet.frozen_amount if wallet else 0),
                    "total_amount": _format_amount(wallet.total_amount if wallet else 0),
                    "status": row.status,
                    "status_text": dict(Withdraw.STATUS_CHOICES).get(row.status, "--"),
                    "audit_user_name": (row.audit_user.fullname or row.audit_user.username) if row.audit_user else "--",
                    "audit_remark": row.audit_remark or "--",
                    "can_approve": is_admin and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                    "can_reject": is_admin and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                    "can_cancel": int(row.user_id) == int(current_user_id) and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                }
            )

        summary = None
        if is_admin:
            summary = {
                "approved_total": _format_amount(qs.filter(status=Withdraw.STATUS_APPROVED).aggregate(total=Sum("amount")).get("total") or 0),
                "pending_total": _format_amount(qs.filter(status=Withdraw.STATUS_PENDING_APPROVAL).aggregate(total=Sum("amount")).get("total") or 0),
                "pending_count": qs.filter(status=Withdraw.STATUS_PENDING_APPROVAL).count(),
            }

        return Response(
            {
                "count": count,
                "page": page,
                "limit": limit,
                "results": results,
                "summary": summary,
                "is_admin": is_admin,
                "message": "查询成功",
            }
        )


class WithdrawApproveView(APIView):
    """管理员审批通过提现申请。"""

    @extend_schema(
        summary="审批通过提现申请",
        tags=["wallet"],
        parameters=[
            OpenApiParameter(name="id", description="提现申请ID", required=True, type=str),
        ],
        request=None,
        responses={200: None, 400: dict, 401: dict, 403: dict, 404: dict},
    )
    def post(self, request, id: int):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)
        if not _is_admin(current_user_id):
            return Response({"message": "无权限操作"}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            withdraw = Withdraw.objects.select_for_update().filter(id=id).first()
            if not withdraw:
                return Response({"message": "提现申请不存在"}, status=status.HTTP_404_NOT_FOUND)
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response({"message": "当前状态不可审批"}, status=status.HTTP_400_BAD_REQUEST)

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(withdraw.amount):
                return Response({"message": "冻结金额不足，无法审批"}, status=status.HTTP_400_BAD_REQUEST)

            before_amount = _quantize_amount(wallet.total_amount)
            wallet.frozen_amount = _quantize_amount(wallet.frozen_amount - withdraw.amount)
            wallet.total_amount = _quantize_amount(wallet.total_amount - withdraw.amount)
            wallet.save(update_fields=["frozen_amount", "total_amount"])

            withdraw.status = Withdraw.STATUS_APPROVED
            withdraw.audit_user_id = current_user_id
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = "同意"
            withdraw.save(update_fields=["status", "audit_user", "audit_time", "audit_remark"])

            WalletRecord.objects.create(
                id=generate_snowflake_id(),
                user_id=withdraw.user_id,
                amount=-_quantize_amount(withdraw.amount),
                before_amount=before_amount,
                after_amount=_quantize_amount(wallet.total_amount),
                remark="提现审批通过",
                created_at=timezone.now(),
            )

        return Response({"message": "审批通过成功"})


class WithdrawRejectView(APIView):
    """管理员拒绝提现申请，并解冻资金。"""

    @extend_schema(
        summary="拒绝提现申请",
        tags=["wallet"],
        parameters=[
            OpenApiParameter(name="id", description="提现申请ID", required=True, type=str),
        ],
        request=None,
        responses={200: None, 400: dict, 401: dict, 403: dict, 404: dict},
    )
    def post(self, request, id: int):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)
        if not _is_admin(current_user_id):
            return Response({"message": "无权限操作"}, status=status.HTTP_403_FORBIDDEN)

        audit_remark = str(request.data.get("audit_remark", "")).strip()
        if not audit_remark:
            return Response({"message": "请填写审批意见"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            withdraw = Withdraw.objects.select_for_update().filter(id=id).first()
            if not withdraw:
                return Response({"message": "提现申请不存在"}, status=status.HTTP_404_NOT_FOUND)
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response({"message": "当前状态不可审批"}, status=status.HTTP_400_BAD_REQUEST)

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(withdraw.amount):
                return Response({"message": "冻结金额不足，无法驳回"}, status=status.HTTP_400_BAD_REQUEST)

            wallet.frozen_amount = _quantize_amount(wallet.frozen_amount - withdraw.amount)
            wallet.available_amount = _quantize_amount(wallet.available_amount + withdraw.amount)
            wallet.save(update_fields=["frozen_amount", "available_amount"])

            withdraw.status = Withdraw.STATUS_REJECTED
            withdraw.audit_user_id = current_user_id
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = audit_remark
            withdraw.save(update_fields=["status", "audit_user", "audit_time", "audit_remark"])

        return Response({"message": "审批拒绝成功"})


class WithdrawCancelView(APIView):
    """用户自行作废提现申请，并解冻资金。"""

    @extend_schema(
        summary="作废提现申请",
        tags=["wallet"],
        parameters=[
            OpenApiParameter(name="id", description="提现申请ID", required=True, type=str),
        ],
        request=None,
        responses={200: None, 400: dict, 401: dict, 403: dict, 404: dict},
    )
    def post(self, request, id: int):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        with transaction.atomic():
            withdraw = Withdraw.objects.select_for_update().filter(id=id).first()
            if not withdraw:
                return Response({"message": "提现申请不存在"}, status=status.HTTP_404_NOT_FOUND)
            if int(withdraw.user_id) != int(current_user_id):
                return Response({"message": "仅能作废自己的提现申请"}, status=status.HTTP_403_FORBIDDEN)
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response({"message": "当前状态不可作废"}, status=status.HTTP_400_BAD_REQUEST)

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(withdraw.amount):
                return Response({"message": "冻结金额不足，无法作废"}, status=status.HTTP_400_BAD_REQUEST)

            wallet.frozen_amount = _quantize_amount(wallet.frozen_amount - withdraw.amount)
            wallet.available_amount = _quantize_amount(wallet.available_amount + withdraw.amount)
            wallet.save(update_fields=["frozen_amount", "available_amount"])

            withdraw.status = Withdraw.STATUS_CANCELLED
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = "用户作废"
            withdraw.save(update_fields=["status", "audit_time", "audit_remark"])

        return Response({"message": "作废成功"})
