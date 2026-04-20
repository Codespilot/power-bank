from decimal import Decimal, ROUND_HALF_UP

from .serializers import SafeBigIntModelSerializer
from rest_framework import serializers
from .models import User, UserAsset


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
        fields = ["id", "username", "fullname", "phone", "email", "superior_id", "superior_phone", "superior_agent", "agent_rate", "created_at", "total_asset", "locked_out"]

    def get_total_asset(self, obj):
        asset = UserAsset.objects.filter(id=obj.id).first()
        return str(asset.total_amount) if asset else "0.00"

    def get_superior_id(self, obj):
        return str(obj.agent_id) if obj.agent_id else None

    def get_superior_phone(self, obj):
        superior = getattr(obj, "agent", None)
        if not superior and obj.agent_id:
            superior = User.objects.filter(id=obj.agent_id).first()
        return superior.phone if superior and superior.phone else None

    def get_agent_rate(self, obj):
        return _format_agent_rate(obj.agent_rate, bool(obj.agent_id))

    def get_superior_agent(self, obj):
        return _get_superior_agent_display(obj)

class UserCreateSerializer(SafeBigIntModelSerializer):
    class Meta:
        model = User
        fields = ["username", "fullname", "phone", "email", "password_hash"]

class UserDetailSerializer(SafeBigIntModelSerializer):
    total_asset = serializers.SerializerMethodField()
    superior_id = serializers.SerializerMethodField()
    superior_phone = serializers.SerializerMethodField()
    superior_agent = serializers.SerializerMethodField()
    agent_rate = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "fullname", "phone", "email", "superior_id", "superior_phone", "superior_agent", "agent_rate", "created_at", "total_asset"]

    def get_total_asset(self, obj):
        asset = UserAsset.objects.filter(id=obj.id).first()
        return str(asset.total_amount) if asset else "0.00"

    def get_superior_id(self, obj):
        return str(obj.agent_id) if obj.agent_id else None

    def get_superior_phone(self, obj):
        superior = getattr(obj, "agent", None)
        if not superior and obj.agent_id:
            superior = User.objects.filter(id=obj.agent_id).first()
        return superior.phone if superior and superior.phone else None

    def get_agent_rate(self, obj):
        return _format_agent_rate(obj.agent_rate, bool(obj.agent_id))

    def get_superior_agent(self, obj):
        return _get_superior_agent_display(obj)
