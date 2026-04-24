from rest_framework import serializers


# ============ 邀请码管理 Request/Response Serializers ============

class InviteCodeListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    count = serializers.IntegerField()
    results = serializers.ListField(child=serializers.DictField())


class InviteCodeCreateRequestSerializer(serializers.Serializer):
    rate = serializers.DecimalField(max_digits=5, decimal_places=4, required=True, help_text="分润比例 (例如: 0.01)")


class InviteCodeCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = serializers.DictField()


class InviteCodeToggleResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    is_valid = serializers.BooleanField()
