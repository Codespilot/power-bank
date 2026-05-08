import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from api.message import ResponseMessage
from utils.generate_snowflake_id import generate_snowflake_id

from ..exceptions import CredentialError
from ..serializers import CommonResponseSerializer, GenericResponseSerializer
from ..views import BaseAPIView
from ..models import BankCard, Attachment, UserRole
from ..auth import create_file_access_token

from .bankcard_serializers import (
    BankCardListResponseSerializer,
    BankCardDetailResponseSerializer,
    BankCardCreateRequestSerializer,
    BankCardUpdateRequestSerializer,
    BankCardLookupSerializer,
)

import logging

logger = logging.getLogger(__name__)


def _check_admin(request):
    """检查当前用户是否为管理员。"""
    from api.auth import get_request_user_id
    user_id = get_request_user_id(request)
    if not user_id:
        raise CredentialError("未登录")
    is_admin = UserRole.objects.filter(user_id=user_id, role=UserRole.ROLE_ADMIN).exists()
    return user_id, bool(is_admin)


def _mask_id_no(id_no: str) -> str:
    """隐藏身份证号中间6位。"""
    if not id_no:
        return ""
    id_no = str(id_no).strip()
    length = len(id_no)
    if length <= 6:
        return id_no
    if length <= 10:
        return id_no[:3] + "*" * (length - 6) + id_no[-3:]
    return id_no[:4] + "*" * (length - 6) + id_no[-2:]


def _build_file_url(file_name: str) -> str:
    """根据attachment的file_name构建完整的可访问文件URL。"""
    if not file_name:
        return ""
    try:
        attachment = Attachment.objects.get(file_name=file_name)
        token = create_file_access_token(
            file_name=attachment.file_name,
            file_ext=attachment.file_ext,
            signature_key=attachment.signature_key,
        )
        base_url = getattr(settings, "BASE_URL", "")
        return f"{base_url}/files/attachments/{attachment.file_name}?token={token}"
    except Attachment.DoesNotExist:
        return ""


def _serialize_bankcard(card, include_file_names: bool = False) -> dict:
    """序列化银行卡数据。"""
    data = {
        "id": str(card.id),
        "card_no": card.card_no,
        "name": card.name,
        "id_no": _mask_id_no(card.id_no),
        "mobile": card.mobile or "",
        "card_photo_url": _build_file_url(card.card_photo),
        "id_photo_badge_url": _build_file_url(card.id_photo_badge),
        "id_photo_face_url": _build_file_url(card.id_photo_face),
        "is_default": card.is_default,
        "user_id": str(card.user_id),
        "created_at": BaseAPIView.format_datetime(card.created_at),
    }
    if include_file_names:
        data["card_photo"] = card.card_photo or ""
        data["id_photo_badge"] = card.id_photo_badge or ""
        data["id_photo_face"] = card.id_photo_face or ""
    return data


class BankCardListView(BaseAPIView):
    """银行卡列表查询接口。"""

    @extend_schema(
        summary="银行卡列表",
        tags=["bankcards"],
        parameters=[
            OpenApiParameter(name="keyword", description="搜索关键词（银行卡号、身份证号、持卡人姓名、预留手机号）", required=False),
            OpenApiParameter(name="page", description="页码，默认为1", required=False),
            OpenApiParameter(name="limit", description="每页数量，默认为10", required=False),
        ],
        responses={200: GenericResponseSerializer[BankCardListResponseSerializer]},
    )
    def get(self, request):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            qs = BankCard.objects.select_related("user").order_by("-created_at", "-id")

            if not is_admin:
                qs = qs.filter(user_id=current_user_id)

            keyword = str(request.GET.get("keyword", "")).strip()
            if keyword:
                qs = qs.filter(
                    Q(card_no__icontains=keyword)
                    | Q(id_no__icontains=keyword)
                    | Q(name__icontains=keyword)
                    | Q(mobile__icontains=keyword)
                )

            page = int(request.GET.get("page", 1) or 1)
            limit = int(request.GET.get("limit", 10) or 10)
            if page <= 0:
                page = 1
            if limit <= 0:
                limit = 10
            offset = (page - 1) * limit

            count = qs.count()
            page_rows = list(qs[offset: offset + limit])
            results = [_serialize_bankcard(row) for row in page_rows]

            return Response({
                "count": count,
                "page": page,
                "limit": limit,
                "results": results,
                "message": "查询成功",
            })

        return self.invoke(_handle)

    @extend_schema(
        tags=["bankcards"],
        summary="新增银行卡",
        description="新增银行卡信息。银行卡号不能重复。",
        request=BankCardCreateRequestSerializer,
        responses={200: CommonResponseSerializer, 400: CommonResponseSerializer},
    )
    def post(self, request):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            print(current_user_id, is_admin)

            card_no = str(request.data.get("card_no", "")).strip()
            name = str(request.data.get("name", "")).strip()
            id_no = str(request.data.get("id_no", "")).strip()
            mobile = str(request.data.get("mobile", "")).strip()
            card_photo = str(request.data.get("card_photo", "")).strip()
            id_photo_badge = str(request.data.get("id_photo_badge", "")).strip()
            id_photo_face = str(request.data.get("id_photo_face", "")).strip()
            is_default = request.data.get("is_default", False)

            if isinstance(is_default, str):
                is_default = is_default.lower() in ("true", "1", "yes")

            if not card_no:
                raise ValueError("银行卡号不能为空")
            if not re.match(r"^\d{6,32}$", card_no):
                raise ValueError("银行卡号格式错误，必须为纯数字")
            if not name:
                raise ValueError("持卡人姓名不能为空")
            if not id_no:
                raise ValueError("身份证号不能为空")

            # 校验银行卡号唯一
            if BankCard.objects.filter(card_no=card_no).exists():
                raise ValueError("银行卡号已存在")

            # 校验附件是否存在（仅当提供了值）
            photo_fields = {
                "card_photo": card_photo,
                "id_photo_badge": id_photo_badge,
                "id_photo_face": id_photo_face,
            }
            for fname in photo_fields.values():
                if fname and not Attachment.objects.filter(file_name=fname).exists():
                    raise ValueError(f"附件「{fname}」不存在")

            # 空字符串转为None，以便数据库存储NULL
            def _blank_to_none(v):
                return v if v else None

            with transaction.atomic():
                card = BankCard.objects.create(
                    id=generate_snowflake_id(),
                    user_id=current_user_id,
                    card_no=card_no,
                    name=name,
                    id_no=id_no,
                    mobile=mobile,
                    card_photo=_blank_to_none(card_photo),
                    id_photo_badge=_blank_to_none(id_photo_badge),
                    id_photo_face=_blank_to_none(id_photo_face),
                    is_default=is_default,
                )

            return Response({
                "id": str(card.id),
                "message": "新增成功",
            })

        return self.invoke(_handle)


class BankCardDetailView(BaseAPIView):
    """银行卡详情、编辑、删除接口。"""

    @extend_schema(
        tags=["bankcards"],
        summary="获取银行卡详情",
        description="查询指定银行卡的详细信息。非管理员只能查看自己的银行卡。",
        responses={200: BankCardDetailResponseSerializer, 404: dict},
    )
    def get(self, request, id):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            try:
                card = BankCard.objects.get(id=id)
            except BankCard.DoesNotExist:
                return Response(ResponseMessage("银行卡不存在", status.HTTP_404_NOT_FOUND), status=status.HTTP_404_NOT_FOUND)

            if not is_admin and int(card.user_id) != int(current_user_id):
                return Response(ResponseMessage("无权限查看", status.HTTP_403_FORBIDDEN), status=status.HTTP_403_FORBIDDEN)

            return Response({**_serialize_bankcard(card, include_file_names=True), "message": "查询成功"})

        return self.invoke(_handle)

    @extend_schema(
        tags=["bankcards"],
        summary="编辑银行卡",
        description="修改银行卡信息。非管理员只能修改自己的银行卡。",
        request=BankCardUpdateRequestSerializer,
        responses={200: CommonResponseSerializer, 400: CommonResponseSerializer, 404: CommonResponseSerializer, 403: CommonResponseSerializer},
    )
    def post(self, request, id):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            try:
                card = BankCard.objects.get(id=id)
            except BankCard.DoesNotExist:
                return Response({"message": "银行卡不存在"}, status=status.HTTP_404_NOT_FOUND)

            if not is_admin and int(card.user_id) != int(current_user_id):
                return Response({"message": "无权限修改"}, status=status.HTTP_403_FORBIDDEN)

            card_no = str(request.data.get("card_no", "")).strip()
            name = str(request.data.get("name", "")).strip()
            id_no = str(request.data.get("id_no", "")).strip()
            mobile = str(request.data.get("mobile", "")).strip()
            card_photo = str(request.data.get("card_photo", "")).strip()
            id_photo_badge = str(request.data.get("id_photo_badge", "")).strip()
            id_photo_face = str(request.data.get("id_photo_face", "")).strip()
            is_default = request.data.get("is_default")

            if card_no:
                if not re.match(r"^\d{6,32}$", card_no):
                    raise ValueError("银行卡号格式错误，必须为纯数字")
                if BankCard.objects.filter(card_no=card_no).exclude(id=id).exists():
                    raise ValueError("银行卡号已存在")
                card.card_no = card_no

            if name:
                card.name = name
            if id_no:
                card.id_no = id_no
            if mobile is not None:
                card.mobile = mobile
            if card_photo:
                if not Attachment.objects.filter(file_name=card_photo).exists():
                    raise ValueError(f"附件「{card_photo}」不存在")
                card.card_photo = card_photo
            if id_photo_badge:
                if not Attachment.objects.filter(file_name=id_photo_badge).exists():
                    raise ValueError(f"附件「{id_photo_badge}」不存在")
                card.id_photo_badge = id_photo_badge
            if id_photo_face:
                if not Attachment.objects.filter(file_name=id_photo_face).exists():
                    raise ValueError(f"附件「{id_photo_face}」不存在")
                card.id_photo_face = id_photo_face
            if is_default is not None:
                if isinstance(is_default, str):
                    is_default = is_default.lower() in ("true", "1", "yes")
                card.is_default = is_default

            card.save()
            return Response(ResponseMessage("修改成功"))

        return self.invoke(_handle)

    @extend_schema(
        tags=["bankcards"],
        summary="删除银行卡",
        description="删除指定银行卡。非管理员只能删除自己的银行卡。",
        responses={200: CommonResponseSerializer, 404: CommonResponseSerializer, 403: CommonResponseSerializer},
    )
    def delete(self, request, id):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            try:
                card = BankCard.objects.get(id=id)
            except BankCard.DoesNotExist:
                return Response(ResponseMessage("银行卡不存在", status.HTTP_404_NOT_FOUND), status=status.HTTP_404_NOT_FOUND)

            if not is_admin and int(card.user_id) != int(current_user_id):
                return Response(ResponseMessage("无权限删除", status.HTTP_403_FORBIDDEN), status=status.HTTP_403_FORBIDDEN)

            card.delete()
            return Response(ResponseMessage("删除成功"))

        return self.invoke(_handle)


class BankCardLookupView(BaseAPIView):
    """银行卡下拉列表接口。"""

    @extend_schema(
        tags=["bankcards"],
        summary="银行卡下拉列表",
        description="返回当前用户的银行卡下拉列表，仅包含id、card_no、name三个字段。",
        responses={200: BankCardLookupSerializer(many=True)},
    )
    def get(self, request):
        def _handle():
            current_user_id, is_admin = _check_admin(request)

            qs = BankCard.objects.filter(user_id=current_user_id).order_by("-is_default", "-created_at")
            results = [
                {
                    "id": str(c.id),
                    "card_no": c.card_no,
                    "name": c.name,
                }
                for c in qs
            ]
            return Response({
                "results": results,
                "message": "查询成功",
            })

        return self.invoke(_handle)
