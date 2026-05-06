from rest_framework import serializers

class ProfitRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="分润记录ID")
    settle_date = serializers.DateField(help_text="结算日期")
    agent_id = serializers.IntegerField(help_text="代理商ID")
    agent_fullname = serializers.CharField(help_text="代理商姓名")
    agent_username = serializers.CharField(help_text="代理商用户名")
    agent_phone = serializers.CharField(help_text="代理商手机号")
    order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="订单金额")
    profit_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="分润金额")
    settle_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="结算金额")
    settle_source = serializers.CharField(help_text="结算来源")
    settle_source_text = serializers.CharField(help_text="结算来源描述")
    source_fullname = serializers.CharField(help_text="来源姓名")
    source_username = serializers.CharField(help_text="来源用户名")
    source_phone = serializers.CharField(help_text="来源手机号")
    rate = serializers.DecimalField(max_digits=5, decimal_places=2, help_text="分润率")
    created_at = serializers.DateTimeField(help_text="记录创建时间", format="%Y-%m-%d %H:%M:%S")
