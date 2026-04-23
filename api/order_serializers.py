from rest_framework import serializers
from .models import Order, OrderImport
from .serializers import SafeBigIntModelSerializer

# ============ 商户管理 Request/Response Serializers ============

class MerchantListRequestSerializer(serializers.Serializer):
    merchant_name = serializers.CharField(required=False, allow_blank=True, help_text="商户名称关键字")
    agent_keyword = serializers.CharField(required=False, allow_blank=True, help_text="代理商关键字（手机号/姓名/用户名/邮箱）")
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")

class MerchantListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(help_text="总数")
    page = serializers.IntegerField(help_text="当前页码")
    limit = serializers.IntegerField(help_text="每页数量")
    message = serializers.CharField()
    results = serializers.ListField(child=serializers.DictField())

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

# ============ 邀请码管理 Request/Response Serializers ============

class InviteCodeListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    count = serializers.IntegerField()
    results = serializers.ListField(child=serializers.DictField())

class InviteCodeCreateRequestSerializer(serializers.Serializer):
    rate = serializers.CharField(required=True, help_text="分润比例 (例如: 0.01)")

class InviteCodeCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = serializers.DictField()

class InviteCodeToggleResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    is_valid = serializers.BooleanField()

class OrderSerializer(SafeBigIntModelSerializer):
    order_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    bill_date = serializers.DateTimeField(format="%Y-%m-%d", required=False, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    is_capped = serializers.SerializerMethodField()
    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'order_date', 'bill_month', 'bill_date', 'order_type', 'order_amount',
            'merchant_name', 'merchant_profit', 'agent_profit', 'is_capped', 'created_at'
        ]
    def get_is_capped(self, obj):
        # 假设有字段或逻辑判断是否封顶计费
        return getattr(obj, 'is_capped', False)

class OrderImportSerializer(SafeBigIntModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    profit_run_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    can_run_profit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    def get_can_run_profit(self, obj):
        return obj.profit_task_status in (
            OrderImport.PROFIT_STATUS_NOT_STARTED,
            OrderImport.PROFIT_STATUS_FAILED,
        ) and obj.status != OrderImport.STATUS_RUNNING

    def get_can_delete(self, obj):
        return (
            obj.status != OrderImport.STATUS_RUNNING
            and obj.profit_task_status != OrderImport.PROFIT_STATUS_RUNNING
        )

    class Meta:
        model = OrderImport
        fields = '__all__'
