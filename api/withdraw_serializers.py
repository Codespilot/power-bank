from rest_framework import serializers
from rest_framework.fields import Field

class WithdrawListRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, help_text="页码")
    limit = serializers.IntegerField(required=False, default=10, help_text="每页数量")
    date_start = serializers.CharField(required=False, allow_blank=True, help_text="起始日期 (YYYY-MM-DD)")
    date_end = serializers.CharField(required=False, allow_blank=True, help_text="结束日期 (YYYY-MM-DD)")

class WithdrawListResponseSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="提现申请ID")
    created_at = serializers.CharField(help_text="申请时间")
    applicant_display = serializers.CharField(help_text="申请人")
    amount = serializers.CharField(help_text="申请金额")
    available_amount = serializers.CharField(help_text="可用余额")
    frozen_amount = serializers.CharField(help_text="冻结余额")
    total_amount = serializers.CharField(help_text="累计余额")
    status = serializers.IntegerField(help_text="状态：0=待审批，1=已批准，2=已驳回，3=已作废")
    status_text = serializers.CharField(help_text="状态文本")
    audit_user_name = serializers.CharField(help_text="审核人")
    audit_remark = serializers.CharField(help_text="审核备注")
    can_approve = serializers.BooleanField(help_text="是否可审批")
    can_reject = serializers.BooleanField(help_text="是否可驳回")
    can_cancel = serializers.BooleanField(help_text="是否可作废")
