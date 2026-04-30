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

    PAYMENT_METHOD_CARD = "card"
    PAYMENT_METHOD_QR = "qr"
    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_METHOD_CARD, "银行卡"),
        (PAYMENT_METHOD_QR, "收款码"),
    )

    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="withdraws")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    remark = models.CharField(max_length=500, null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES)
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True,
        verbose_name="收款方式",
    )
    bank_card_id = models.BigIntegerField(null=True, blank=True, verbose_name="银行卡ID")
    bank_card_no = models.CharField(max_length=32, null=True, blank=True, verbose_name="银行卡号")
    bank_card_holder = models.CharField(max_length=50, null=True, blank=True, verbose_name="持卡人姓名")
    receiving_qr_code = models.CharField(max_length=50, null=True, blank=True, verbose_name="收款码照片")
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


class Term(BaseEntity):
    """
    系统协议/条款管理。

    Attributes:
        id: 主键，通过SnowflakeId产生
        type: 协议类型，1-隐私政策、2-用户协议
        name: 协议名称
        platform: 平台，1-全部、2-Web、3-小程序、4-App、5-其他
        status: 状态，1-待发布、2-已发布，默认1
        content: 协议内容，html或markdown文本
        file_name: 发布时生成的文件名，通常为UUID.html
        is_valid: 是否有效，默认1
        created_at: 创建时间
        updated_at: 修改时间
        published_at: 发布时间
    """
    TYPE_PRIVACY = 1
    TYPE_USER_AGREEMENT = 2
    TYPE_CHOICES = (
        (TYPE_PRIVACY, "隐私政策"),
        (TYPE_USER_AGREEMENT, "用户协议"),
    )

    PLATFORM_ALL = 1
    PLATFORM_WEB = 2
    PLATFORM_MINI = 3
    PLATFORM_APP = 4
    PLATFORM_OTHER = 5
    PLATFORM_CHOICES = (
        (PLATFORM_ALL, "全部"),
        (PLATFORM_WEB, "Web"),
        (PLATFORM_MINI, "小程序"),
        (PLATFORM_APP, "App"),
        (PLATFORM_OTHER, "其他"),
    )

    STATUS_DRAFT = 1
    STATUS_PUBLISHED = 2
    STATUS_CHOICES = (
        (STATUS_DRAFT, "待发布"),
        (STATUS_PUBLISHED, "已发布"),
    )

    id = models.BigIntegerField(primary_key=True)
    type = models.IntegerField(choices=TYPE_CHOICES, verbose_name="协议类型")
    name = models.CharField(max_length=100, verbose_name="协议名称")
    platform = models.IntegerField(
        choices=PLATFORM_CHOICES, null=True, blank=True, verbose_name="平台"
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name="状态"
    )
    content = models.TextField(verbose_name="协议内容")
    file_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="文件名")
    is_valid = models.BooleanField(default=True, verbose_name="是否有效")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="修改时间")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="发布时间")

    class Meta:
        db_table = "term"
        app_label = "api"
        verbose_name = "协议管理"
        verbose_name_plural = "协议管理"


class Attachment(BaseEntity):
    """
    附件/文件管理。

    Attributes:
        id: 主键，通过SnowflakeId产生
        file_name: 存储在磁盘上的文件名，UUID格式
        origin_name: 用户上传时的原始文件名
        file_size: 文件大小（字节）
        file_ext: 文件扩展名，如 .jpg、.png、.pdf
        signature_key: 用于签名文件访问token的密钥
        upload_by: 上传用户
        created_at: 上传时间
    """
    id = models.BigIntegerField(primary_key=True)
    file_name = models.CharField(max_length=50, unique=True, verbose_name="存储文件名")
    origin_name = models.CharField(max_length=255, verbose_name="原始文件名")
    file_size = models.BigIntegerField(default=0, verbose_name="文件大小")
    file_ext = models.CharField(max_length=10, verbose_name="文件扩展名")
    signature_key = models.CharField(max_length=64, verbose_name="签名密钥")
    upload_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        db_column="upload_by",
        related_name="attachments",
        null=True,
        blank=True,
        verbose_name="上传用户",
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="上传时间")

    class Meta:
        db_table = "attachment"
        app_label = "api"
        verbose_name = "附件管理"
        verbose_name_plural = "附件管理"


class BankCard(BaseEntity):
    """
    用户银行卡信息。

    Attributes:
        id: 主键，通过SnowflakeId产生
        user: 外键，关联到 User 模型
        card_no: 银行卡号，纯数字，保存前去除空格，不能重复
        name: 持卡人姓名
        id_no: 身份证号
        mobile: 银行预留手机号
        card_photo: 银行卡照片，对应attachment表的file_name
        id_photo_badge: 身份证国徽面照片，对应attachment表的file_name
        id_photo_face: 身份证人像面照片，对应attachment表的file_name
        is_default: 是否默认
        created_at: 创建时间
    """
    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="bank_cards",
    )
    card_no = models.CharField(max_length=32, unique=True, verbose_name="银行卡号")
    name = models.CharField(max_length=50, verbose_name="持卡人姓名")
    id_no = models.CharField(max_length=18, verbose_name="身份证号")
    mobile = models.CharField(max_length=20, null=True, blank=True, verbose_name="预留手机号")
    card_photo = models.CharField(max_length=50, verbose_name="银行卡照片")
    id_photo_badge = models.CharField(max_length=50, verbose_name="身份证国徽照片")
    id_photo_face = models.CharField(max_length=50, verbose_name="身份证人像照片")
    is_default = models.BooleanField(default=False, verbose_name="是否默认")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        db_table = "bank_card"
        app_label = "api"
        verbose_name = "银行卡管理"
        verbose_name_plural = "银行卡管理"
