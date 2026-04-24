from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth import get_request_user_id
from api.message import ResponseMessage
from utils.generate_snowflake_id import generate_snowflake_id

from ..models import InviteCode
from ..user.user_serializers import _format_agent_rate
from ..user.user_views import _parse_agent_rate
from drf_spectacular.utils import OpenApiParameter, extend_schema
from ..serializers import GenericResponseSerializer, CommonResponseSerializer
from .invite_serializers import (
    InviteCodeListResponseSerializer,
    InviteCodeCreateRequestSerializer,
)


def _build_invite_link(request, code: str) -> str:
    """根据当前请求上下文拼接可直接访问的注册邀请链接。"""
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host() or "localhost"
    return f"{scheme}://{host}/register?invite_code={code}"


def _serialize_invite_code(request, invite: InviteCode):
    """将邀请码对象转换为前端表格需要的展示结构。"""
    rate_decimal = Decimal(str(invite.rate or "0.00"))
    percent_value = (rate_decimal * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "id": str(invite.id),
        "code": invite.code,
        "rate": _format_agent_rate(invite.rate, True),
        "rate_percent_value": str(percent_value),
        "register_count": int(invite.register_count or 0),
        "is_valid": bool(invite.is_valid),
        "status_text": "启用" if invite.is_valid else "作废",
        "created_at": (
            invite.created_at.strftime("%Y-%m-%d %H:%M:%S") if invite.created_at else ""
        ),
        "invite_link": _build_invite_link(request, invite.code),
    }


class InviteCodeView(APIView):
    @extend_schema(
        tags=["invite-codes"],
        methods=["GET"],
        summary="获取邀请码列表",
        description="查询当前用户的所有邀请码及其注册统计信息。",
        responses={
            200: GenericResponseSerializer[InviteCodeListResponseSerializer],
            401: CommonResponseSerializer(),
        },
    )
    def get(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录", "code": 401}, status=status.HTTP_401_UNAUTHORIZED)

        queryset = InviteCode.objects.filter(user_id=user_id).order_by("-created_at")
        results = [_serialize_invite_code(request, item) for item in queryset]
        return Response(
            {"message": "查询成功", "code": 200, "count": len(results), "results": results}
        )

    @extend_schema(
        tags=["invite-codes"],
        methods=["POST"],
        summary="创建邀请码",
        description="为当前用户创建新的邀请码，需指定分润比例。",
        request=InviteCodeCreateRequestSerializer,
        responses={
            200: CommonResponseSerializer,
            400: CommonResponseSerializer(),
            401: CommonResponseSerializer(),
        },
    )
    def post(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response(ResponseMessage("未登录", 401).to_dict(), status=status.HTTP_401_UNAUTHORIZED)

        try:
            rate = _parse_agent_rate(request.data.get("rate", ""))
        except Exception as exc:
            return Response(
                ResponseMessage(str(exc) or "分润比例格式错误", 400).to_dict(),
                status=status.HTTP_400_BAD_REQUEST,
            )

        invite = InviteCode.objects.create(
            id=generate_snowflake_id(),
            user_id=user_id,
            rate=rate,
            register_count=0,
            is_valid=True,
            created_at=timezone.now(),
        )
        return Response(ResponseMessage("新增邀请码成功", 200).to_dict())


class InviteCodeToggleView(APIView):
    @extend_schema(
        tags=["invite-codes"],
        request=None,
        summary="切换邀请码状态",
        description="启用或作废指定的邀请码。",
        parameters=[
            OpenApiParameter(
                name="id",
                description="邀请码ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses={
            200: CommonResponseSerializer(),
            401: CommonResponseSerializer(),
            404: CommonResponseSerializer(),
            500: CommonResponseSerializer(),
        },
    )
    def post(self, request, id=None):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response(ResponseMessage("未登录", 401).to_dict(), status=status.HTTP_401_UNAUTHORIZED)

        invite = InviteCode.objects.filter(id=id, user_id=user_id).first()
        if not invite:
            return Response(
                ResponseMessage("邀请码不存在", 404).to_dict(), status=status.HTTP_404_NOT_FOUND
            )

        invite.is_valid = not bool(invite.is_valid)
        invite.save(update_fields=["is_valid"])
        action = "启用" if invite.is_valid else "作废"
        return Response(ResponseMessage(f"邀请码已{action}", 200).to_dict())
