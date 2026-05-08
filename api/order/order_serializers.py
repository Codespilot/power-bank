from rest_framework import serializers
from ..models import Order, OrderImport
from ..serializers import SafeBigIntModelSerializer

class OrderSerializer(SafeBigIntModelSerializer):
    id = serializers.IntegerField(help_text="订单ID，整数")
    order_no = serializers.CharField(help_text="订单号")
    order_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", help_text="订单日期，格式为 YYYY-MM-DD")
    bill_date = serializers.DateTimeField(format="%Y-%m-%d", required=False, allow_null=True, help_text="账单日期，格式为 YYYY-MM-DD")
    bill_month = serializers.IntegerField(help_text="账单月份，格式为 YYYYMM")
    order_type = serializers.CharField(help_text="订单类型")
    order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="订单金额，保留两位小数")
    merchant_name = serializers.CharField(help_text="商户名称")
    merchant_profit = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="商户分润金额，保留两位小数")
    agent_profit = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="代理商分润金额，保留两位小数")
    agent_id = serializers.IntegerField(help_text="代理商ID，整数")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True, help_text="创建时间，格式为 YYYY-MM-DD HH:MM:SS")
    is_capped = serializers.SerializerMethodField(help_text="是否封顶计费")
    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'order_date', 'bill_month', 'bill_date', 'order_type', 'order_amount',
            'merchant_name', 'merchant_profit', 'agent_profit', 'agent_id', 'is_capped', 'created_at'
        ]
    def get_is_capped(self, obj):
        # 假设有字段或逻辑判断是否封顶计费
        return getattr(obj, 'is_capped', False)

class OrderImportSerializer(SafeBigIntModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", help_text="创建时间，格式为 YYYY-MM-DD HH:MM:SS")
    profit_run_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True, help_text="分润执行时间，格式为 YYYY-MM-DD HH:MM:SS")
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
