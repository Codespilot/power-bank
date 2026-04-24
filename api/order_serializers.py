from rest_framework import serializers
from .models import Order, OrderImport
from .serializers import SafeBigIntModelSerializer

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
