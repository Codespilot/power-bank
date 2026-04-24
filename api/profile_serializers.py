from rest_framework import serializers

class UserProfileResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="用户ID")
    username = serializers.CharField(help_text="用户名")
    fullname = serializers.CharField(help_text="全名")
    phone = serializers.CharField(help_text="手机号")
    email = serializers.CharField(help_text="邮箱")
    superior_agent = serializers.CharField(help_text="上级代理")
    agent_rate = serializers.CharField(help_text="代理费率")
    user_is_admin = serializers.BooleanField(help_text="是否为管理员")

class UserProfileUpdateRequestSerializer(serializers.Serializer):
    fullname = serializers.CharField(required=False, allow_blank=True, help_text="全名")
    phone = serializers.CharField(required=False, allow_blank=True, help_text="手机号")
    email = serializers.EmailField(required=False, allow_blank=True, help_text="邮箱")
