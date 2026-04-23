from rest_framework import serializers


# ============ 钱包管理 Request/Response Serializers ============

class WalletInfoSerializer(serializers.Serializer):
    total_amount = serializers.CharField(help_text="总金额")
    frozen_amount = serializers.CharField(help_text="冻结金额")
    pending_amount = serializers.CharField(help_text="待结算金额")
    available_amount = serializers.CharField(help_text="可用金额")
    message = serializers.CharField(help_text="响应消息")


class WalletWithdrawRequestSerializer(serializers.Serializer):
    amount = serializers.CharField(required=True, help_text="提现金额")
    remark = serializers.CharField(required=False, allow_blank=True, help_text="备注信息")


class WalletWithdrawResponseSerializer(serializers.Serializer):
    total_amount = serializers.CharField(help_text="总金额")
    frozen_amount = serializers.CharField(help_text="冻结金额")
    pending_amount = serializers.CharField(help_text="待结算金额")
    available_amount = serializers.CharField(help_text="可用金额")
    withdraw_id = serializers.CharField(help_text="提现申请ID")
    message = serializers.CharField(help_text="响应消息")


class WalletRecordListRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")
    date_from = serializers.CharField(required=False, allow_blank=True, help_text="起始日期 (YYYY-MM-DD)")
    date_to = serializers.CharField(required=False, allow_blank=True, help_text="结束日期 (YYYY-MM-DD)")


class WalletRecordListResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="记录ID")
    amount = serializers.CharField(help_text="变动金额")
    before_amount = serializers.CharField(help_text="变动前金额")
    after_amount = serializers.CharField(help_text="变动后金额")
    remark = serializers.CharField(help_text="备注")
    created_at = serializers.CharField(help_text="创建时间")


class WalletRecordSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="记录ID")
    amount = serializers.CharField(help_text="变动金额")
    before_amount = serializers.CharField(help_text="变动前金额")
    after_amount = serializers.CharField(help_text="变动后金额")
    remark = serializers.CharField(help_text="备注")
    created_at = serializers.CharField(help_text="创建时间")
