import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import User

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{1,32}$")
MOBILE_REGEX = re.compile(r"^1(3[0-9]|4[5-9]|5[0-35-9]|6[2567]|7[0-8]|8[0-9]|9[0-35-9])\d{8}$")
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRES_SECONDS = int(os.getenv("JWT_ACCESS_EXPIRES_SECONDS", "7200"))
JWT_REFRESH_EXPIRES_SECONDS = int(os.getenv("JWT_REFRESH_EXPIRES_SECONDS", str(7 * 24 * 3600)))


def is_valid_username(identifier: str) -> bool:
    return bool(USERNAME_REGEX.fullmatch(identifier) or MOBILE_REGEX.fullmatch(identifier) or EMAIL_REGEX.fullmatch(identifier))


def get_user_by_identifier(identifier: str) -> User | None:
    # 优先用户名精确查找，其次手机号、邮箱
    user = User.objects.filter(username=identifier).first()
    if user:
        return user
    return User.objects.filter(Q(phone=identifier) | Q(email=identifier)).first()


def hash_password(plain_password: str) -> tuple[str, str]:
    password_salt = secrets.token_hex(16)
    password_hash = hashlib.sha256(f"{plain_password}{password_salt}".encode("utf-8")).hexdigest()
    return password_hash, password_salt


def verify_password(user: User, plain_password: str) -> bool:
    salted_sha256 = hashlib.sha256(f"{plain_password}{user.password_salt}".encode("utf-8")).hexdigest()
    return user.password_hash in {plain_password, salted_sha256}


def compute_lock_until(access_failed_count: int):
    if access_failed_count <= 10:
        return None
    lock_minutes = min((access_failed_count - 10) * 10, 24 * 60)
    return timezone.now() + timedelta(minutes=lock_minutes)


def new_captcha_code() -> str:
    return f"{secrets.randbelow(10_000):04d}"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _jwt_secret() -> bytes:
    return settings.SECRET_KEY.encode("utf-8")


def _encode_jwt(payload: dict) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(_jwt_secret(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_jwt(token: str, expected_type: str | None = None) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_signature = hmac.new(_jwt_secret(), signing_input, hashlib.sha256).digest()
        signature = _b64url_decode(signature_b64)
    except (ValueError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise AuthenticationFailed("无效的token")

    if not hmac.compare_digest(signature, expected_signature):
        raise AuthenticationFailed("token签名校验失败")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise AuthenticationFailed("无效的token载荷")

    exp = int(payload.get("exp", 0))
    if exp <= int(timezone.now().timestamp()):
        raise AuthenticationFailed("token已过期")

    token_type = str(payload.get("type", ""))
    if expected_type and token_type != expected_type:
        raise AuthenticationFailed("token类型错误")

    return payload


def create_access_token(user: User) -> tuple[str, int]:
    now_ts = int(timezone.now().timestamp())
    exp = now_ts + JWT_ACCESS_EXPIRES_SECONDS
    payload = {
        "type": "access",
        "user_id": int(user.id),
        "username": user.username,
        "iat": now_ts,
        "exp": exp,
    }
    return _encode_jwt(payload), JWT_ACCESS_EXPIRES_SECONDS


def create_refresh_token(user: User) -> tuple[str, int]:
    now_ts = int(timezone.now().timestamp())
    exp = now_ts + JWT_REFRESH_EXPIRES_SECONDS
    payload = {
        "type": "refresh",
        "user_id": int(user.id),
        "username": user.username,
        "iat": now_ts,
        "exp": exp,
    }
    return _encode_jwt(payload), JWT_REFRESH_EXPIRES_SECONDS


def get_request_user_id(request):
    session_user_id = request.session.get("current_user_id")
    if session_user_id:
        return int(session_user_id)

    request_user = getattr(request, "user", None)
    request_user_id = getattr(request_user, "id", None)
    if request_user_id:
        return int(request_user_id)

    return None


class JWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            raise AuthenticationFailed("Authorization头格式错误")

        payload = decode_jwt(parts[1], expected_type="access")
        user = User.objects.filter(id=payload.get("user_id")).first()
        if not user:
            raise AuthenticationFailed("用户不存在")

        return (user, payload)
