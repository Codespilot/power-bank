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
    id = serializers.CharField(help_text="历史记录ID")
    merchant_id = serializers.IntegerField(help_text="商户ID")
    merchant_name = serializers.CharField(help_text="商户名称")
    new_agent = serializers.CharField(help_text="新代理商信息（姓名-手机号）")
    new_agent_id = serializers.IntegerField(help_text="新代理商ID")
    new_agent_fullname = serializers.CharField(help_text="新代理商姓名")
    new_agent_phone = serializers.CharField(help_text="新代理商手机号")
    old_agent = serializers.CharField(help_text="旧代理商信息（姓名-手机号）")
    old_agent_id = serializers.IntegerField(help_text="旧代理商ID")
    old_agent_fullname = serializers.CharField(help_text="旧代理商姓名")
    old_agent_phone = serializers.CharField(help_text="旧代理商手机号")
    created_at = serializers.DateTimeField(help_text="变更时间")


class MerchantHistoryPageResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(help_text="总数")
    page = serializers.IntegerField(help_text="当前页码")
    limit = serializers.IntegerField(help_text="每页数量")
    results = MerchantHistoryResponseSerializer(many=True, help_text="历史记录列表")
    message = serializers.CharField()


class MerchantAssignAgentRequestSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField(required=False, allow_null=True, help_text="代理商用户ID，与agent_phone二选一")
    agent_phone = serializers.CharField(required=False, allow_blank=True, help_text="代理商手机号，与agent_id二选一")


class MerchantBatchAssignAgentRequestSerializer(serializers.Serializer):
    merchant_ids = serializers.ListField(child=serializers.IntegerField(), required=True, help_text="商户ID列表")
    agent_id = serializers.IntegerField(required=False, allow_null=True, help_text="代理商用户ID，与agent_phone二选一")
    agent_phone = serializers.CharField(required=False, allow_blank=True, help_text="代理商手机号，与agent_id二选一")


class MerchantHistoryListRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")


class MerchantAssignMessageSerializer(serializers.Serializer):
    message = serializers.CharField(help_text="操作结果信息")
