from rest_framework import serializers


# ============ 邀请码管理 Request/Response Serializers ============


class InviteCodeListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="邀请码ID")
    code = serializers.CharField(help_text="邀请码", max_length=10)
    rate = serializers.CharField(help_text="分润比例文本展示")
    rate_percent_value = serializers.CharField(help_text="分润比例百分数值（字符串格式）")
    register_count = serializers.IntegerField(help_text="通过该邀请码注册的用户数量")
    is_valid = serializers.BooleanField(help_text="邀请码是否有效")
    status_text = serializers.CharField(help_text="邀请码状态文本（启用/作废）")
    created_at = serializers.CharField(help_text="邀请码创建时间（字符串格式）")
    invite_link = serializers.CharField(help_text="邀请码链接（如果code存在）")


class InviteCodeCreateRequestSerializer(serializers.Serializer):
    rate = serializers.DecimalField(
        max_digits=5, decimal_places=4, required=True, help_text="分润比例 (例如: 0.01)"
    )
