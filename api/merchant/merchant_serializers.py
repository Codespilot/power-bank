from rest_framework import serializers


class MerchantListRequestSerializer(serializers.Serializer):
    merchant_name = serializers.CharField(required=False, allow_blank=True, help_text="商户名称关键字")
    agent_keyword = serializers.CharField(required=False, allow_blank=True, help_text="代理商关键字（手机号/姓名/用户名/邮箱）")
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")


class MerchantListResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="商户ID")
    merchant_id = serializers.CharField(help_text="商户编号")
    merchant_name = serializers.CharField(help_text="商户名称")
    agent_fullname = serializers.CharField(help_text="代理商姓名")
    agent_phone = serializers.CharField(help_text="代理商手机号")
    order_count = serializers.IntegerField(help_text="订单数量")
    order_amount = serializers.DecimalField(max_digits=18, decimal_places=2, help_text="订单总金额")
    merchant_profit = serializers.DecimalField(max_digits=18, decimal_places=2, help_text="商户分润总金额")


class MerchantHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(help_text="总数")
    message = serializers.CharField()
    results = serializers.ListField(child=serializers.DictField())


class MerchantAssignAgentRequestSerializer(serializers.Serializer):
    agent_phone = serializers.CharField(required=True, help_text="代理商手机号")


class MerchantBatchAssignAgentRequestSerializer(serializers.Serializer):
    merchant_ids = serializers.ListField(child=serializers.IntegerField(), required=True, help_text="商户ID列表")
    agent_phone = serializers.CharField(required=True, help_text="代理商手机号")


class MerchantAssignMessageSerializer(serializers.Serializer):
    message = serializers.CharField(help_text="操作结果信息")
