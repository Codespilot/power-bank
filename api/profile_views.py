import re

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth import EMAIL_REGEX, MOBILE_REGEX, get_request_user_id
from django.http import HttpRequest

from api.profile_serializers import (
    UserProfileResponseSerializer,
    UserProfileUpdateRequestSerializer,
)
from .models import User, UserRole
from .user_serializers import _format_agent_rate, _get_superior_agent_display


class UserProfileView(APIView):
    def _build_invite_link(self, request: HttpRequest, code: str) -> str:
        if not code:
            return ""
        scheme = "https" if request.is_secure() else "http"
        host = request.get_host() or "localhost"
        return f"{scheme}://{host}/register?invite_code={code}"

    def _get_current_user(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return None
        return User.objects.select_related("agent").filter(id=user_id).first()

    @extend_schema(
        summary="获取个人资料",
        tags=["profile"],
        request=None,
        responses={200: UserProfileResponseSerializer, 400: dict, 401: dict},
    )
    def get(self, request):
        user = self._get_current_user(request)
        if not user:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        is_admin = UserRole.objects.filter(
            user_id=user.id, role=UserRole.ROLE_ADMIN
        ).exists()
        return Response(
            {
                "id": str(user.id),
                "username": user.username,
                "fullname": user.fullname or "",
                "phone": user.phone or "",
                "email": user.email or "",
                "superior_agent": _get_superior_agent_display(user),
                "agent_rate": _format_agent_rate(user.agent_rate, bool(user.agent_id)),
                "user_is_admin": is_admin,
            }
        )

    @extend_schema(
        summary="更新个人资料",
        tags=["profile"],
        request=UserProfileUpdateRequestSerializer,
        responses={200: dict, 400: dict, 401: dict},
    )
    def post(self, request):
        user = self._get_current_user(request)
        if not user:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        fullname = str(request.data.get("fullname", "")).strip()
        phone = str(request.data.get("phone", "")).strip()
        email = str(request.data.get("email", "")).strip()

        if not fullname:
            return Response(
                {"message": "姓名不能为空"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not MOBILE_REGEX.fullmatch(phone):
            return Response(
                {"message": "手机号格式错误"}, status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.exclude(id=user.id).filter(phone=phone).exists():
            return Response(
                {"message": "手机号已存在"}, status=status.HTTP_400_BAD_REQUEST
            )

        if email:
            if not EMAIL_REGEX.fullmatch(email):
                return Response(
                    {"message": "邮箱格式错误"}, status=status.HTTP_400_BAD_REQUEST
                )
            if User.objects.exclude(id=user.id).filter(email=email).exists():
                return Response(
                    {"message": "邮箱已存在"}, status=status.HTTP_400_BAD_REQUEST
                )

        user.fullname = fullname
        user.phone = phone
        user.email = email or None
        user.save(update_fields=["fullname", "phone", "email"])
        return Response({"message": "资料修改成功"})
