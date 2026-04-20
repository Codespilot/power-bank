from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth import get_request_user_id
from utils.generate_snowflake_id import generate_snowflake_id

from .models import InviteCode
from .user_serializers import _format_agent_rate
from .user_views import _parse_agent_rate


def _build_invite_link(request, code: str) -> str:
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host() or "localhost"
    return f"{scheme}://{host}/register?invite_code={code}"


def _serialize_invite_code(request, invite: InviteCode):
    rate_decimal = Decimal(str(invite.rate or "0.00"))
    percent_value = (rate_decimal * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "id": str(invite.id),
        "code": invite.code,
        "rate": _format_agent_rate(invite.rate, True),
        "rate_percent_value": str(percent_value),
        "register_count": int(invite.register_count or 0),
        "is_valid": bool(invite.is_valid),
        "status_text": "启用" if invite.is_valid else "作废",
        "created_at": invite.created_at.strftime("%Y-%m-%d %H:%M:%S") if invite.created_at else "",
        "invite_link": _build_invite_link(request, invite.code),
    }


class InviteCodeListCreateView(APIView):
    def get(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        queryset = InviteCode.objects.filter(user_id=user_id).order_by("-created_at")
        results = [_serialize_invite_code(request, item) for item in queryset]
        return Response({"message": "查询成功", "count": len(results), "results": results})

    def post(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            rate = _parse_agent_rate(request.data.get("rate", ""))
        except Exception as exc:
            return Response({"message": str(exc) or "分润比例格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        invite = InviteCode.objects.create(
            id=generate_snowflake_id(),
            user_id=user_id,
            rate=rate,
            register_count=0,
            is_valid=True,
            created_at=timezone.now(),
        )
        return Response({"message": "新增邀请码成功", "data": _serialize_invite_code(request, invite)})


class InviteCodeToggleView(APIView):
    def post(self, request, id=None):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        invite = InviteCode.objects.filter(id=id, user_id=user_id).first()
        if not invite:
            return Response({"message": "邀请码不存在"}, status=status.HTTP_404_NOT_FOUND)

        invite.is_valid = not bool(invite.is_valid)
        invite.save(update_fields=["is_valid"])
        action = "启用" if invite.is_valid else "作废"
        return Response({"message": f"邀请码已{action}", "is_valid": invite.is_valid})
