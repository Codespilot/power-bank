from decimal import Decimal, ROUND_HALF_UP

from .serializers import SafeBigIntModelSerializer
from rest_framework import serializers
from .models import User, Wallet


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class IdMessageSerializer(MessageSerializer):
    id = serializers.CharField(required=False)
    user_id = serializers.CharField(required=False)
    next = serializers.CharField(required=False, allow_blank=True)


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, help_text="用户名、手机号或邮箱")
    password = serializers.CharField(required=True, write_only=True)
    captcha = serializers.CharField(required=False, allow_blank=True)
    source_token = serializers.CharField(required=False, allow_blank=True)
    next = serializers.CharField(required=False, allow_blank=True)


class TokenRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=True)


class TokenGrantResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    token_type = serializers.CharField()
    access_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    refresh_token = serializers.CharField()
    refresh_expires_in = serializers.IntegerField()
    user_id = serializers.CharField()


class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    fullname = serializers.CharField(required=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    captcha = serializers.CharField(required=True)
    invite_code = serializers.CharField(required=True)


class AgentAssignSerializer(serializers.Serializer):
    subordinate_id = serializers.CharField(required=False, allow_blank=True)
    superior_id = serializers.CharField(required=False, allow_blank=True)
    superior_phone = serializers.CharField(required=False, allow_blank=True)
    rate = serializers.CharField(required=True)


class UserResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, write_only=True)


def _get_superior_agent_display(obj):
    if not obj.agent_id:
        return "--"
    superior = getattr(obj, "agent", None)
    if not superior:
        superior = User.objects.filter(id=obj.agent_id).first()
    if not superior:
        return "--"

    display_name = (superior.fullname or "").strip() or superior.username
    return f"{display_name}（{superior.phone}）" if superior.phone else display_name


def _format_agent_rate(rate, has_superior=False):
    if not has_superior:
        return "--"
    value = Decimal(str(rate or '0'))
    percent = (value * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f"{percent}%"


class UserListSerializer(SafeBigIntModelSerializer):
    phone = serializers.CharField()
    email = serializers.CharField()
    total_asset = serializers.SerializerMethodField()
    superior_id = serializers.SerializerMethodField()
    superior_phone = serializers.SerializerMethodField()
    superior_agent = serializers.SerializerMethodField()
    agent_rate = serializers.SerializerMethodField()
    locked_out = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = User
        fields = ["id", "username", "fullname", "phone", "email", "invite_code", "superior_id", "superior_phone", "superior_agent", "agent_rate", "created_at", "total_asset", "locked_out"]

    def get_total_asset(self, obj) -> str:
        wallet = Wallet.objects.filter(id=obj.id).first()
        return str(wallet.total_amount) if wallet else "0.00"

    def get_superior_id(self, obj) -> str | None:
        return str(obj.agent_id) if obj.agent_id else None

    def get_superior_phone(self, obj) -> str | None:
        superior = getattr(obj, "agent", None)
        if not superior and obj.agent_id:
            superior = User.objects.filter(id=obj.agent_id).first()
        return superior.phone if superior and superior.phone else None

    def get_agent_rate(self, obj) -> str:
        return _format_agent_rate(obj.agent_rate, bool(obj.agent_id))

    def get_superior_agent(self, obj) -> str:
        return _get_superior_agent_display(obj)


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    fullname = serializers.CharField(required=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=True, write_only=True)
    superior_phone = serializers.CharField(required=False, allow_blank=True)
    agent_rate = serializers.CharField(required=False, allow_blank=True)

class UserDetailSerializer(SafeBigIntModelSerializer):
    total_asset = serializers.SerializerMethodField()
    superior_id = serializers.SerializerMethodField()
    superior_phone = serializers.SerializerMethodField()
    superior_agent = serializers.SerializerMethodField()
    agent_rate = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["id", "username", "fullname", "phone", "email", "invite_code", "superior_id", "superior_phone", "superior_agent", "agent_rate", "created_at", "total_asset"]

    def get_total_asset(self, obj) -> str:
        wallet = Wallet.objects.filter(id=obj.id).first()
        return str(wallet.total_amount) if wallet else "0.00"

    def get_superior_id(self, obj) -> str | None:
        return str(obj.agent_id) if obj.agent_id else None

    def get_superior_phone(self, obj) -> str | None:
        superior = getattr(obj, "agent", None)
        if not superior and obj.agent_id:
            superior = User.objects.filter(id=obj.agent_id).first()
        return superior.phone if superior and superior.phone else None

    def get_agent_rate(self, obj) -> str:
        return _format_agent_rate(obj.agent_rate, bool(obj.agent_id))

    def get_superior_agent(self, obj) -> str:
        return _get_superior_agent_display(obj)


class TokenGrantSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, help_text="用户名、手机号或邮箱")
    password = serializers.CharField(required=True, write_only=True)
