from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from decimal import Decimal
import secrets
import string

from django.utils import timezone
from utils.generate_snowflake_id import generate_snowflake_id


# ===== 核心数据模型 =====
# 本文件集中定义用户、邀请码、钱包、商户、订单、分润等核心业务实体。


def _generate_unique_invite_code(model_cls):
    """生成全局唯一的邀请码，供 InviteCode 模型复用。"""
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not model_cls.objects.filter(code=code).exists():
            return code
    raise ValueError("无法生成唯一邀请码")


class BaseEntity(models.Model):
    """项目公共抽象基类，统一声明 app_label。"""

    class Meta:
        abstract = True
        app_label = "api"

class User(BaseEntity):
    """系统用户。

    agent / agent_rate 表示当前用户与其上级代理之间的直属关系。
    invite_code 字段保存注册时使用的邀请码，而不是用户自己生成的邀请码列表。
    """
    id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=32, unique=True)
    fullname = models.CharField(max_length=64, default="")
    phone = models.CharField(max_length=11, unique=True)
    email = models.CharField(max_length=255, unique=True, null=True, blank=True)
    invite_code = models.CharField(max_length=8, null=True, blank=True)
    password_hash = models.CharField(max_length=512)
    password_salt = models.CharField(max_length=64)
    locked_out = models.DateTimeField(null=True, blank=True)
    access_failed_count = models.IntegerField(default=0)
    agent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        db_column="agent_id",
        related_name="subordinates",
        null=True,
        blank=True,
    )
    agent_rate = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("1.00"))],
    )
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        normalized_invite_code = str(self.invite_code or "").strip().lower()
        self.invite_code = normalized_invite_code or None
        super().save(*args, **kwargs)

    class Meta:
        db_table = "user"
        app_label = "api"

class UserRole(BaseEntity):
    """
    用户角色

    Attributes:
        id: 主键
        user: 外键，关联到 User 模型
        role: 角色名称，枚举值（admin、user）
        created_at: 记录创建时间
    """
    ROLE_ADMIN = "admin"
    ROLE_USER = "user"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "admin"),
        (ROLE_USER, "user"),
    )

    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="roles")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_USER)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "user_role"
        app_label = "api"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uq_user_role_user_id_role"),
        ]


class AgentHistory(BaseEntity):
    """
    代理商变更记录

    Attributes:
        id: 主键
        old_superior: 外键，变更前的上级代理商，允许为空
        new_superior: 外键，变更后的上级代理商，允许为空
        created_at: 记录创建时间
    """
    id = models.BigIntegerField(primary_key=True)
    old_superior = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="old_superior_id",
        related_name="old_agent_histories",
        null=True,
        blank=True,
    )
    new_superior = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="new_superior_id",
        related_name="new_agent_histories",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "agent_history"
        app_label = "api"


class Merchant(BaseEntity):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, db_column="agent_id", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "merchant"
        app_label = "api"


class MerchantHistory(BaseEntity):
    id = models.BigIntegerField(primary_key=True)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, db_column="merchant_id", related_name="histories")
    old_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="old_agent_id",
        related_name="merchant_old_agent_histories",
        null=True,
        blank=True,
    )
    new_agent = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="new_agent_id",
        related_name="merchant_new_agent_histories",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "merchant_history"
        app_label = "api"


class Order(BaseEntity):
    id = models.BigIntegerField(primary_key=True)
    import_id = models.BigIntegerField(db_index=True)
    order_no = models.CharField(max_length=64, unique=True, default="", blank=False)
    order_date = models.DateTimeField()
    bill_month = models.IntegerField(null=True, blank=True)
    bill_date = models.DateTimeField(null=True, blank=True, db_index=True)
    order_type = models.CharField(max_length=10)
    order_amount = models.DecimalField(max_digits=18, decimal_places=2)
    merchant_name = models.CharField(max_length=255)
    merchant_id = models.BigIntegerField(db_index=True)
    merchant_profit = models.DecimalField(max_digits=18, decimal_places=2)
    agent_profit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "order"
        app_label = "api"


class ProfitAllocation(BaseEntity):
    """代理分润明细。

    一条记录表示某个用户在某个结算日得到的一笔 direct 或 subagent 分润。
    """
    SOURCE_DIRECT = "direct"
    SOURCE_SUBAGENT = "subagent"
    SOURCE_CHOICES = (
        (SOURCE_DIRECT, "direct"),
        (SOURCE_SUBAGENT, "subagent"),
    )

    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="profit_allocations")
    settle_source_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="settle_source_user_id",
        related_name="source_profit_allocations",
        null=True,
        blank=True,
    )
    rate = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("1.00"))],
    )
    profit_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    order_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    settle_amount = models.DecimalField(max_digits=18, decimal_places=2)
    settle_date = models.DateTimeField(null=True, blank=True)
    settle_source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    order_import_id = models.BigIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "profit_allocation"
        app_label = "api"


class InviteCode(BaseEntity):
    """邀请码记录。

    每个邀请码绑定一个生成人和一个默认分润比例，可用于邀请下级注册。
    """
    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="invite_codes")
    code = models.CharField(max_length=8, unique=True)
    rate = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("1.00"))],
    )
    register_count = models.IntegerField(default=0)
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _generate_unique_invite_code(InviteCode)
        else:
            self.code = str(self.code).strip().lower()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "invite_code"
        app_label = "api"


class OrderImport(BaseEntity):
    STATUS_NOT_STARTED = 1
    STATUS_RUNNING = 2
    STATUS_SUCCESS = 3
    STATUS_FAILED = 4
    STATUS_CHOICES = (
        (STATUS_NOT_STARTED, "未开始"),
        (STATUS_RUNNING, "运行中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    )

    PROFIT_STATUS_NOT_STARTED = 1
    PROFIT_STATUS_RUNNING = 2
    PROFIT_STATUS_SUCCESS = 3
    PROFIT_STATUS_FAILED = 4
    PROFIT_STATUS_CHOICES = (
        (PROFIT_STATUS_NOT_STARTED, "未运行"),
        (PROFIT_STATUS_RUNNING, "正在运行"),
        (PROFIT_STATUS_SUCCESS, "完成"),
        (PROFIT_STATUS_FAILED, "失败"),
    )

    id = models.BigIntegerField(primary_key=True)
    file_name = models.CharField(max_length=128)
    succeed_rows = models.IntegerField(null=True, blank=True)
    failed_rows = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES)
    profit_task_status = models.IntegerField(
        choices=PROFIT_STATUS_CHOICES,
        default=PROFIT_STATUS_NOT_STARTED,
    )
    profit_run_time = models.DateTimeField(null=True, blank=True)
    profit_error_message = models.TextField(null=True, blank=True)
    profit_summary_count = models.IntegerField(default=0)
    profit_total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "order_import"
        app_label = "api"


class Wallet(BaseEntity):
    """用户钱包。

    通过用户 id 与用户一一对应，保存总额、冻结额、在途额和可用额。
    """
    id = models.BigIntegerField(primary_key=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    frozen_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    pending_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    available_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "wallet"
        app_label = "api"


class WalletRecord(BaseEntity):
    """钱包流水记录。

    before_amount 和 after_amount 记录的是本次变动前后的可用金额。
    """
    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="wallet_records")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    before_amount = models.DecimalField(max_digits=18, decimal_places=2)
    after_amount = models.DecimalField(max_digits=18, decimal_places=2)
    remark = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "wallet_record"
        app_label = "api"


class Withdraw(BaseEntity):
    STATUS_PENDING_SUBMIT = 1
    STATUS_PENDING_APPROVAL = 2
    STATUS_APPROVED = 3
    STATUS_REJECTED = 4
    STATUS_CANCELLED = 5
    STATUS_CHOICES = (
        (STATUS_PENDING_SUBMIT, "待提交"),
        (STATUS_PENDING_APPROVAL, "待审批"),
        (STATUS_APPROVED, "通过"),
        (STATUS_REJECTED, "拒绝"),
        (STATUS_CANCELLED, "作废"),
    )

    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="withdraws")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    remark = models.CharField(max_length=500, null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES)
    audit_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="audit_user_id",
        related_name="audited_withdraws",
        null=True,
        blank=True,
    )
    audit_time = models.DateTimeField(null=True, blank=True)
    audit_remark = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "withdraw"
        app_label = "api"

class Item(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

class ProfitTaskRecord(models.Model):
    """
    分润任务运行记录
    Attributes:
        id: 主键，使用雪花算法生成
        run_time: 任务实际运行时间
        duration: 任务持续时间，单位毫秒
        bill_date: 任务运行查询的单据日期范围
        data_scanned: 任务处理的数据量（例如订单数量）
        profit_data_count: 产生的分润记录数量
        error_message: 任务执行过程中捕获的错误信息，若无错误则为 null
        created_at: 记录创建时间
    """
    id = models.BigIntegerField(primary_key=True)
    run_time = models.DateTimeField(default=timezone.now)
    duration = models.IntegerField(default=0)
    bill_date = models.CharField(max_length=32, default="")
    data_scanned = models.IntegerField(default=0)
    profit_data_count = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "profit_task"
        app_label = "api"
