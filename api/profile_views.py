import re

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth import EMAIL_REGEX, MOBILE_REGEX, get_request_user_id, hash_password, verify_password
from django.http import HttpRequest
from .models import InviteCode, User, UserRole
from .user_serializers import _format_agent_rate, _get_superior_agent_display


class CurrentUserProfileView(APIView):
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

    def get(self, request):
        user = self._get_current_user(request)
        if not user:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        is_admin = UserRole.objects.filter(user_id=user.id, role=UserRole.ROLE_ADMIN).exists()
        latest_invite = InviteCode.objects.filter(user_id=user.id, is_valid=True).order_by('-created_at').first()
        invite_link = self._build_invite_link(request, latest_invite.code if latest_invite else "")
        return Response(
            {
                "id": str(user.id),
                "username": user.username,
                "fullname": user.fullname or "",
                "phone": user.phone or "",
                "email": user.email or "",
                "invite_code": latest_invite.code if latest_invite else "",
                "invite_link": invite_link,
                "superior_agent": _get_superior_agent_display(user),
                "agent_rate": _format_agent_rate(user.agent_rate, bool(user.agent_id)),
                "user_is_admin": is_admin,
                "message": "查询成功",
            }
        )

    def post(self, request):
        user = self._get_current_user(request)
        if not user:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        fullname = str(request.data.get("fullname", "")).strip()
        phone = str(request.data.get("phone", "")).strip()
        email = str(request.data.get("email", "")).strip()

        if not fullname:
            return Response({"message": "姓名不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        if not MOBILE_REGEX.fullmatch(phone):
            return Response({"message": "手机号格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.exclude(id=user.id).filter(phone=phone).exists():
            return Response({"message": "手机号已存在"}, status=status.HTTP_400_BAD_REQUEST)

        if email:
            if not EMAIL_REGEX.fullmatch(email):
                return Response({"message": "邮箱格式错误"}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.exclude(id=user.id).filter(email=email).exists():
                return Response({"message": "邮箱已存在"}, status=status.HTTP_400_BAD_REQUEST)

        user.fullname = fullname
        user.phone = phone
        user.email = email or None
        user.save(update_fields=["fullname", "phone", "email"])
        return Response({"message": "资料修改成功"})


class CurrentUserPasswordView(APIView):
    def post(self, request):
        user_id = get_request_user_id(request)
        if not user_id:
            return Response({"message": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"message": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        old_password = str(request.data.get("old_password", ""))
        new_password = str(request.data.get("new_password", ""))
        confirm_password = str(request.data.get("confirm_password", ""))

        if not verify_password(user, old_password):
            return Response({"message": "原密码错误"}, status=status.HTTP_400_BAD_REQUEST)

        if not new_password or len(new_password) < 6:
            return Response({"message": "新密码至少6位"}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"message": "两次输入的新密码不一致"}, status=status.HTTP_400_BAD_REQUEST)

        password_hash, password_salt = hash_password(new_password)
        user.password_hash = password_hash
        user.password_salt = password_salt
        user.save(update_fields=["password_hash", "password_salt"])
        return Response({"message": "密码修改成功"})
