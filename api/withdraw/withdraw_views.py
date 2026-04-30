from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.exceptions import CredentialError
from utils.generate_snowflake_id import generate_snowflake_id

from ..auth import create_file_access_token, get_request_user_id
from ..models import (
    Attachment,
    BankCard,
    User,
    UserRole,
    Wallet,
    WalletRecord,
    Withdraw,
)
from ..serializers import GenericResponseSerializer, CommonResponseSerializer
from ..message import ResponseMessage
from .withdraw_serializers import (
    WithdrawCreateRequestSerializer,
    WithdrawListResponseSerializer,
)

_AMOUNT_QUANT = Decimal("0.01")


def _wallet_defaults() -> dict:
    return {
        "total_amount": Decimal("0.00"),
        "frozen_amount": Decimal("0.00"),
        "pending_amount": Decimal("0.00"),
        "available_amount": Decimal("0.00"),
    }


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


def _build_qr_code_url(file_name: str) -> str:
    """根据receiving_qr_code构建完整的可访问文件URL。"""
    if not file_name:
        return ""
    try:
        attachment = Attachment.objects.get(file_name=file_name)
        token = create_file_access_token(
            file_name=attachment.file_name,
            file_ext=attachment.file_ext,
            signature_key=attachment.signature_key,
        )
        from django.conf import settings

        base_url = getattr(settings, "BASE_URL", "")
        return f"{base_url}/files/attachments/{attachment.file_name}?token={token}"
    except Attachment.DoesNotExist:
        return ""


class WithdrawView(APIView):
    """
    提现申请视图，支持提交提现申请和查询提现申请列表。
    """

    @extend_schema(
        summary="提现申请列表",
        tags=["withdraws"],
        parameters=[
            OpenApiParameter(
                name="keyword",
                description="搜索关键词，匹配用户名、姓名、手机号、邮箱",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                description="申请状态，0=待审批，1=已批准，2=已驳回，3=已作废",
                required=False,
            ),
            OpenApiParameter(
                name="date_start",
                description="申请开始日期，格式YYYY-MM-DD",
                required=False,
            ),
            OpenApiParameter(
                name="date_end",
                description="申请结束日期，格式YYYY-MM-DD",
                required=False,
            ),
            OpenApiParameter(name="page", description="页码，默认为1", required=False),
            OpenApiParameter(
                name="limit", description="每页数量，默认为10", required=False
            ),
        ],
        responses={200: GenericResponseSerializer[WithdrawListResponseSerializer]},
    )
    def get(self, request):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                {"count": 0, "results": [], "message": "未登录"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        is_admin = _is_admin(current_user_id)
        qs = Withdraw.objects.select_related("user", "audit_user").order_by(
            "-created_at", "-id"
        )

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
                start_dt = timezone.make_aware(
                    datetime.combine(
                        datetime.strptime(date_start, "%Y-%m-%d").date(), dt_time.min
                    )
                )
                qs = qs.filter(created_at__gte=start_dt)
            if date_end:
                end_dt = timezone.make_aware(
                    datetime.combine(
                        datetime.strptime(date_end, "%Y-%m-%d").date(), dt_time.min
                    )
                ) + timedelta(days=1)
                qs = qs.filter(created_at__lt=end_dt)
        except ValueError:
            return Response(
                {"count": 0, "results": [], "message": "日期格式错误"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page = int(request.GET.get("page", 1) or 1)
        limit = int(request.GET.get("limit", 10) or 10)
        if page <= 0:
            page = 1
        if limit <= 0:
            limit = 10
        offset = (page - 1) * limit

        count = qs.count()
        page_rows = list(qs[offset : offset + limit])
        wallets = Wallet.objects.in_bulk([row.user_id for row in page_rows])

        results = []
        for row in page_rows:
            wallet = wallets.get(row.user_id)
            payment_method_text = dict(Withdraw.PAYMENT_METHOD_CHOICES).get(
                row.payment_method, "--"
            )
            results.append(
                {
                    "id": str(row.id),
                    "created_at": _format_datetime(row.created_at),
                    "applicant_display": _display_user(row.user),
                    "amount": _format_amount(row.amount),
                    "frozen_amount": _format_amount(
                        wallet.frozen_amount if wallet else 0
                    ),
                    "payment_method": row.payment_method or "",
                    "payment_method_text": payment_method_text,
                    "bank_card_no": row.bank_card_no or "--",
                    "bank_card_holder": row.bank_card_holder or "--",
                    "receiving_qr_code": row.receiving_qr_code or "",
                    "receiving_qr_code_url": (
                        _build_qr_code_url(row.receiving_qr_code)
                        if row.receiving_qr_code
                        else ""
                    ),
                    "status": row.status,
                    "status_text": dict(Withdraw.STATUS_CHOICES).get(row.status, "--"),
                    "audit_user_name": (
                        (row.audit_user.fullname or row.audit_user.username)
                        if row.audit_user
                        else "--"
                    ),
                    "audit_remark": row.audit_remark or "--",
                    "can_approve": is_admin
                    and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                    "can_reject": is_admin
                    and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                    "can_cancel": int(row.user_id) == int(current_user_id)
                    and row.status == Withdraw.STATUS_PENDING_APPROVAL,
                }
            )

        summary = None
        if is_admin:
            summary = {
                "approved_total": _format_amount(
                    qs.filter(status=Withdraw.STATUS_APPROVED)
                    .aggregate(total=Sum("amount"))
                    .get("total")
                    or 0
                ),
                "pending_total": _format_amount(
                    qs.filter(status=Withdraw.STATUS_PENDING_APPROVAL)
                    .aggregate(total=Sum("amount"))
                    .get("total")
                    or 0
                ),
                "pending_count": qs.filter(
                    status=Withdraw.STATUS_PENDING_APPROVAL
                ).count(),
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

    @extend_schema(
        tags=["withdraws"],
        summary="申请提现",
        description="提交提现申请，冻结相应金额并生成提现申请单。",
        request=WithdrawCreateRequestSerializer,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer,
            401: CommonResponseSerializer,
        },
    )
    def post(self, request):
        try:
            current_user_id = get_request_user_id(request)
            if not current_user_id:
                raise CredentialError("未登录")

            amount = _quantize_amount(request.data.get("amount", "0"))

            if amount < Decimal("0.01"):
                return Response(
                    {"message": "提现金额不能低于0.01"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bank_card_id = None
            bank_card_no = None
            bank_card_holder = None
            receiving_qr_code = None

            bank_card_id_str = str(request.data.get("bank_card_id", "")).strip()
            qr_code_value = str(request.data.get("receiving_qr_code", "")).strip()

            if not bank_card_id_str and not qr_code_value:
                raise ValueError("请选择银行卡或上传收款码照片")

            if bank_card_id_str:
                if not bank_card_id_str.isdigit():
                    raise ValueError("银行卡参数错误")
                bank_card = BankCard.objects.filter(
                    id=int(bank_card_id_str), user_id=current_user_id
                ).first()
                if not bank_card:
                    raise ValueError("银行卡不存在")
                bank_card_id = int(bank_card.id)
                bank_card_no = bank_card.card_no
                bank_card_holder = bank_card.name

            if qr_code_value:
                attachment = Attachment.objects.filter(file_name=qr_code_value).first()  # 验证文件存在
                if not attachment:
                    raise ValueError("收款码文件不存在")
                receiving_qr_code = attachment.file_name

            with transaction.atomic():
                if (
                    Withdraw.objects.select_for_update()
                    .filter(
                        user_id=current_user_id,
                        status__in=[
                            Withdraw.STATUS_PENDING_SUBMIT,
                            Withdraw.STATUS_PENDING_APPROVAL,
                        ],
                    )
                    .exists()
                ):
                    raise ValueError("当前有待处理的提现申请，请稍后再试")

                wallet, _ = Wallet.objects.select_for_update().get_or_create(
                    id=current_user_id, defaults=_wallet_defaults()
                )
                before_amount = _quantize_amount(wallet.available_amount)
                if amount > before_amount:
                    raise ValueError("提现金额不能大于可用金额")

                after_amount = _quantize_amount(before_amount - amount)
                wallet.available_amount = after_amount
                wallet.frozen_amount = _quantize_amount(wallet.frozen_amount + amount)
                wallet.save(update_fields=["available_amount", "frozen_amount"])

                remark = (
                    str(request.data.get("remark", "")).strip() or "提现申请，资金冻结"
                )
                withdraw = Withdraw.objects.create(
                    id=generate_snowflake_id(),
                    user_id=current_user_id,
                    amount=amount,
                    remark=remark,
                    status=Withdraw.STATUS_PENDING_APPROVAL,
                    payment_method=None,
                    bank_card_id=bank_card_id,
                    bank_card_no=bank_card_no,
                    bank_card_holder=bank_card_holder,
                    receiving_qr_code=receiving_qr_code,
                    created_at=timezone.now(),
                )

            refreshed_wallet = Wallet.objects.get(id=current_user_id)
            return Response(
                {
                    "total_amount": _format_amount(refreshed_wallet.total_amount),
                    "frozen_amount": _format_amount(refreshed_wallet.frozen_amount),
                    "pending_amount": _format_amount(refreshed_wallet.pending_amount),
                    "available_amount": _format_amount(
                        refreshed_wallet.available_amount
                    ),
                    "withdraw_id": str(withdraw.id),
                    "message": "提现申请已提交",
                }
            )
        except CredentialError:
            return Response(ResponseMessage("未登录", 401).to_dict(), status=status.HTTP_401_UNAUTHORIZED)
        except (TypeError, ValueError, InvalidOperation) as e:
            return Response((ResponseMessage(f"参数错误: {str(e)}", 400).to_dict()), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(ResponseMessage(f"提现申请失败: {str(e)}", 500).to_dict(), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawApproveView(APIView):
    """管理员审批通过提现申请。"""

    @extend_schema(
        summary="审批通过提现申请",
        tags=["withdraws"],
        parameters=[
            OpenApiParameter(
                name="id",
                description="提现申请ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
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
                return Response(
                    {"message": "提现申请不存在"}, status=status.HTTP_404_NOT_FOUND
                )
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response(
                    {"message": "当前状态不可审批"}, status=status.HTTP_400_BAD_REQUEST
                )

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(
                withdraw.amount
            ):
                return Response(
                    ResponseMessage("冻结金额不足，无法审批", 400).to_dict(),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            before_amount = _quantize_amount(wallet.total_amount)
            wallet.frozen_amount = _quantize_amount(
                wallet.frozen_amount - withdraw.amount
            )
            wallet.total_amount = _quantize_amount(
                wallet.total_amount - withdraw.amount
            )
            wallet.save(update_fields=["frozen_amount", "total_amount"])

            withdraw.status = Withdraw.STATUS_APPROVED
            withdraw.audit_user_id = current_user_id
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = "同意"
            withdraw.save(
                update_fields=["status", "audit_user", "audit_time", "audit_remark"]
            )

            WalletRecord.objects.create(
                id=generate_snowflake_id(),
                user_id=withdraw.user_id,
                amount=-_quantize_amount(withdraw.amount),
                before_amount=before_amount,
                after_amount=_quantize_amount(wallet.total_amount),
                remark="提现审批通过",
                created_at=timezone.now(),
            )

        return Response(ResponseMessage("审批通过成功", 200).to_dict())


class WithdrawRejectView(APIView):
    """管理员拒绝提现申请，并解冻资金。"""

    @extend_schema(
        summary="拒绝提现申请",
        tags=["withdraws"],
        parameters=[
            OpenApiParameter(
                name="id",
                description="提现申请ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ],
        request=None,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer,
            401: CommonResponseSerializer,
            403: CommonResponseSerializer,
            404: CommonResponseSerializer,
        },
    )
    def post(self, request, id: int):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                ResponseMessage("未登录", 401).to_dict(),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not _is_admin(current_user_id):
            return Response(
                ResponseMessage("无权限操作", 403).to_dict(),
                status=status.HTTP_403_FORBIDDEN,
            )

        audit_remark = str(request.data.get("audit_remark", "")).strip()
        if not audit_remark:
            return Response(
                ResponseMessage("请填写审批意见", 400).to_dict(),
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            withdraw = Withdraw.objects.select_for_update().filter(id=id).first()
            if not withdraw:
                return Response(
                    ResponseMessage("提现申请不存在", 404).to_dict(),
                    status=status.HTTP_404_NOT_FOUND,
                )
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response(
                    ResponseMessage("当前状态不可审批", 400).to_dict(),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(
                withdraw.amount
            ):
                return Response(
                    ResponseMessage("冻结金额不足，无法驳回", 400).to_dict(),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet.frozen_amount = _quantize_amount(
                wallet.frozen_amount - withdraw.amount
            )
            wallet.available_amount = _quantize_amount(
                wallet.available_amount + withdraw.amount
            )
            wallet.save(update_fields=["frozen_amount", "available_amount"])

            withdraw.status = Withdraw.STATUS_REJECTED
            withdraw.audit_user_id = current_user_id
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = audit_remark
            withdraw.save(
                update_fields=["status", "audit_user", "audit_time", "audit_remark"]
            )

        return Response(ResponseMessage("审批拒绝成功", 200).to_dict())


class WithdrawCancelView(APIView):
    """用户自行作废提现申请，并解冻资金。"""

    @extend_schema(
        summary="作废提现申请",
        tags=["withdraws"],
        parameters=[
            OpenApiParameter(
                name="id",
                description="提现申请ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ],
        request=None,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer,
            401: CommonResponseSerializer,
            403: CommonResponseSerializer,
            404: CommonResponseSerializer,
        },
    )
    def post(self, request, id: int):
        current_user_id = get_request_user_id(request)
        if not current_user_id:
            return Response(
                ResponseMessage("未登录", 401).to_dict(),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        with transaction.atomic():
            withdraw = Withdraw.objects.select_for_update().filter(id=id).first()
            if not withdraw:
                return Response(
                    ResponseMessage("提现申请不存在", 404).to_dict(),
                    status=status.HTTP_404_NOT_FOUND,
                )
            if int(withdraw.user_id) != int(current_user_id):
                return Response(
                    ResponseMessage("仅能作废自己的提现申请", 403).to_dict(),
                    status=status.HTTP_403_FORBIDDEN,
                )
            if withdraw.status != Withdraw.STATUS_PENDING_APPROVAL:
                return Response(
                    ResponseMessage("当前状态不可作废", 400).to_dict(),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                id=withdraw.user_id,
                defaults={
                    "total_amount": Decimal("0.00"),
                    "frozen_amount": Decimal("0.00"),
                    "pending_amount": Decimal("0.00"),
                    "available_amount": Decimal("0.00"),
                },
            )
            if _quantize_amount(wallet.frozen_amount) < _quantize_amount(
                withdraw.amount
            ):
                return Response(
                    ResponseMessage("冻结金额不足，无法作废", 400).to_dict(),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet.frozen_amount = _quantize_amount(
                wallet.frozen_amount - withdraw.amount
            )
            wallet.available_amount = _quantize_amount(
                wallet.available_amount + withdraw.amount
            )
            wallet.save(update_fields=["frozen_amount", "available_amount"])

            withdraw.status = Withdraw.STATUS_CANCELLED
            withdraw.audit_time = timezone.now()
            withdraw.audit_remark = "用户作废"
            withdraw.save(update_fields=["status", "audit_time", "audit_remark"])

        return Response(ResponseMessage("作废成功", 200).to_dict())
