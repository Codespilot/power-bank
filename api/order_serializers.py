from rest_framework import serializers
from .models import MerchantOrder, OrderImport
from .serializers import SafeBigIntModelSerializer

class MerchantOrderSerializer(SafeBigIntModelSerializer):
    order_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    bill_date = serializers.DateTimeField(format="%Y-%m-%d", required=False, allow_null=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, allow_null=True)
    is_capped = serializers.SerializerMethodField()
    class Meta:
        model = MerchantOrder
        fields = [
            'id', 'order_no', 'order_date', 'bill_month', 'bill_date', 'order_type', 'order_amount',
            'merchant_name', 'merchant_profit', 'agent_profit', 'is_capped', 'created_at'
        ]
    def get_is_capped(self, obj):
        # 假设有字段或逻辑判断是否封顶计费
        return getattr(obj, 'is_capped', False)

class OrderImportSerializer(SafeBigIntModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    class Meta:
        model = OrderImport
        fields = '__all__'
