from rest_framework import serializers

class UserProfileResponseSerializer(serializers.Serializer):
    '''用户个人资料响应序列化器，包含用户ID、用户名、全名、手机号、邮箱、上级代理信息、代理费率和管理员状态等字段。'''
    id = serializers.CharField(help_text="用户ID")
    username = serializers.CharField(help_text="用户名")
    fullname = serializers.CharField(help_text="全名")
    phone = serializers.CharField(help_text="手机号")
    email = serializers.CharField(help_text="邮箱")
    superior_agent = serializers.CharField(help_text="上级代理")
    agent_rate = serializers.CharField(help_text="代理费率")
    user_is_admin = serializers.BooleanField(help_text="是否为管理员")
    invite_code = serializers.CharField(help_text="邀请码")

class UserProfileUpdateRequestSerializer(serializers.Serializer):
    '''用户个人资料更新请求序列化器，包含可选的全名、手机号和邮箱字段。'''
    fullname = serializers.CharField(required=False, allow_blank=True, help_text="全名")
    phone = serializers.CharField(required=False, allow_blank=True, help_text="手机号")
    email = serializers.EmailField(required=False, allow_blank=True, help_text="邮箱")
