import logging
from collections import defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    Order,
    OrderImport,
    ProfitAllocation,
    ProfitTaskRecord,
    User,
    Wallet,
    WalletRecord,
)
from utils.generate_snowflake_id import generate_snowflake_id

logger = logging.getLogger(__name__)

_AMOUNT_QUANT = Decimal("0.01")


def _format_bill_date_text(start_text: str, end_text: str) -> str:
    start_text = str(start_text or "").strip()
    end_text = str(end_text or "").strip()
    if not start_text and not end_text:
        return ""
    if not end_text:
        end_text = start_text
    if not start_text:
        start_text = end_text

    try:
        start_obj = datetime.strptime(start_text, "%Y-%m-%d").date()
        end_obj = datetime.strptime(end_text, "%Y-%m-%d").date()
    except ValueError:
        return ""

    start_fmt = start_obj.strftime("%Y.%m.%d")
    end_fmt = end_obj.strftime("%Y.%m.%d")
    if start_obj == end_obj:
        return start_fmt
    return f"{start_fmt} ~ {end_fmt}"


def _quantize_amount(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _to_bill_day_start(bill_day_value) -> datetime:
    if isinstance(bill_day_value, datetime):
        day_value = bill_day_value.date()
    elif isinstance(bill_day_value, date):
        day_value = bill_day_value
    else:
        day_value = datetime.strptime(str(bill_day_value), "%Y-%m-%d").date()
    return timezone.make_aware(datetime.combine(day_value, dt_time.min))


def _fetch_profit_summary_rows(order_import_id: int) -> list[dict]:
    """按导入批次汇总：代理商 + 账单日。"""
    sql = """
        SELECT
            mch.agent_id,
            DATE(odr.bill_date) AS bill_day,
            COUNT(odr.id) AS order_count,
            COALESCE(SUM(odr.order_amount), 0) AS order_amount,
            COALESCE(SUM(odr.merchant_profit), 0) AS merchant_profit
        FROM `order` AS odr
        INNER JOIN merchant AS mch ON odr.merchant_id = mch.id
        WHERE mch.agent_id IS NOT NULL
          AND mch.agent_id > 0
          AND odr.import_id = %s
          AND odr.bill_date IS NOT NULL
        GROUP BY mch.agent_id, DATE(odr.bill_date)
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, [int(order_import_id)])
        rows = cursor.fetchall()

    result = []
    for agent_id, bill_day, order_count, order_amount, merchant_profit in rows:
        if not agent_id or not bill_day:
            continue
        settle_date = _to_bill_day_start(bill_day)
        result.append(
            {
                "agent_id": int(agent_id),
                "settle_date": settle_date,
                "bill_day": settle_date.date().isoformat(),
                "order_count": int(order_count or 0),
                "order_amount": _quantize_amount(Decimal(order_amount or 0)),
                "merchant_profit": _quantize_amount(Decimal(merchant_profit or 0)),
            }
        )
    return result


def _get_superior_chain(agent_id: int) -> list[User]:
    """从当前代理开始向上追溯直属上级链路。

    批量加载所有上级用户，将 N 次独立查询优化为 2 次查询。
    """
    # 第一趟：只采集 agent_id 链路（values_list 仅返回一列，开销极小）
    ids_in_chain: list[int] = []
    visited: set[int] = set()
    current_id = int(agent_id)

    while current_id:
        if current_id in visited:
            logger.warning(
                "Detected cycle while loading superior chain for user %s", agent_id
            )
            break
        visited.add(current_id)
        ids_in_chain.append(current_id)

        next_id = (
            User.objects.filter(id=current_id)
            .values_list("agent_id", flat=True)
            .first()
        )
        if not next_id:
            break
        current_id = int(next_id)

    # 第二趟：批量加载所有用户（1 次查询）
    users_map: dict[int, User] = {
        u.id: u
        for u in User.objects.filter(id__in=ids_in_chain).only(
            "id", "agent_id", "agent_rate"
        )
    }

    return [users_map[uid] for uid in ids_in_chain if uid in users_map]


def _allocate_agent_profit(
    settle_date: datetime,
    agent_id: int,
    total_profit: Decimal,
    total_order_amount: Decimal,
    allocations: dict[
        tuple[datetime, int, str, int | None, Decimal | None],
        dict[str, Decimal | None],
    ],
):
    """按代理链逐级拆分利润。"""
    current_amount = _quantize_amount(total_profit)
    total_profit = _quantize_amount(total_profit)
    total_order_amount = _quantize_amount(total_order_amount)
    current_source = ProfitAllocation.SOURCE_DIRECT
    current_source_user_id: int | None = None
    current_rate: Decimal | None = None
    superior_chain = _get_superior_chain(agent_id)

    for index, agent in enumerate(superior_chain):
        if current_amount <= 0:
            break

        rate = _quantize_amount(Decimal(agent.agent_rate or 0))
        has_next_superior = index + 1 < len(superior_chain)
        key = (
            settle_date,
            int(agent.id),
            current_source,
            current_source_user_id,
            current_rate,
        )

        if not has_next_superior or rate <= 0:
            allocations[key]["settle_amount"] += current_amount
            allocations[key]["profit_amount"] += total_profit
            allocations[key]["order_amount"] += total_order_amount
            break

        superior_share = _quantize_amount(current_amount * rate)
        retained_amount = _quantize_amount(current_amount - superior_share)

        if retained_amount > 0:
            allocations[key]["settle_amount"] += retained_amount
            allocations[key]["profit_amount"] += total_profit
            allocations[key]["order_amount"] += total_order_amount

        if superior_share <= 0:
            break

        current_amount = superior_share
        current_source = ProfitAllocation.SOURCE_SUBAGENT
        current_source_user_id = int(agent.id)
        current_rate = rate


def _update_wallets(
    allocation_deltas: dict[int, Decimal],
    remark_prefix: str,
):
    """根据分润差额更新钱包，支持正向入账和反向回滚。"""
    for user_id, delta in allocation_deltas.items():
        amount = _quantize_amount(delta)
        if amount == 0:
            continue

        wallet, _ = Wallet.objects.select_for_update().get_or_create(
            id=user_id,
            defaults={
                "total_amount": Decimal("0.00"),
                "frozen_amount": Decimal("0.00"),
                "pending_amount": Decimal("0.00"),
                "available_amount": Decimal("0.00"),
            },
        )

        before_amount = _quantize_amount(Decimal(wallet.available_amount or 0))
        after_amount = _quantize_amount(before_amount + amount)
        wallet.total_amount = _quantize_amount(Decimal(wallet.total_amount or 0) + amount)
        wallet.available_amount = after_amount
        wallet.save(update_fields=["total_amount", "available_amount"])

        remark = remark_prefix
        if amount > 0:
            remark = f"{remark_prefix}入账"
        elif amount < 0:
            remark = f"{remark_prefix}回滚"

        WalletRecord.objects.create(
            id=generate_snowflake_id(),
            user_id=user_id,
            amount=amount,
            before_amount=before_amount,
            after_amount=after_amount,
            remark=remark,
            created_at=timezone.now(),
        )


def run_profit_allocation(order_import_id: int) -> dict:
    """按导入记录执行分润。"""
    order_import_id = int(order_import_id)
    profit_rows = _fetch_profit_summary_rows(order_import_id)

    if not profit_rows:
        return {
            "order_import_id": order_import_id,
            "bill_date_start": "",
            "bill_date_end": "",
            "order_count": 0,
            "summary_count": 0,
            "allocation_count": 0,
            "total_settle_amount": "0.00",
            "asset_user_count": 0,
        }

    allocations: dict[
        tuple[datetime, int, str, int | None, Decimal | None],
        dict[str, Decimal | None],
    ] = defaultdict(
        lambda: {
            "settle_amount": Decimal("0.00"),
            "profit_amount": Decimal("0.00"),
            "order_amount": Decimal("0.00"),
        }
    )

    for row in profit_rows:
        _allocate_agent_profit(
            settle_date=row["settle_date"],
            agent_id=row["agent_id"],
            total_profit=row["merchant_profit"],
            total_order_amount=row["order_amount"],
            allocations=allocations,
        )

    total_order_count = sum(row["order_count"] for row in profit_rows)
    bill_days = sorted({row["bill_day"] for row in profit_rows})

    created_count = 0
    asset_user_count = 0
    total_settle_amount = Decimal("0.00")

    with transaction.atomic():
        existing_amounts = {
            int(row["user_id"]): _quantize_amount(Decimal(row["total_amount"] or 0))
            for row in ProfitAllocation.objects.filter(order_import_id=order_import_id)
            .values("user_id")
            .annotate(total_amount=Sum("settle_amount"))
        }

        ProfitAllocation.objects.filter(order_import_id=order_import_id).delete()

        records = []
        new_amounts: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for (
            settle_date,
            user_id,
            source,
            source_user_id,
            rate,
        ), payload in allocations.items():
            settle_amount = _quantize_amount(Decimal(payload["settle_amount"] or 0))
            if settle_amount <= 0:
                continue

            profit_amount = _quantize_amount(Decimal(payload["profit_amount"] or 0))
            order_amount = _quantize_amount(Decimal(payload["order_amount"] or 0))
            total_settle_amount += settle_amount
            new_amounts[int(user_id)] += settle_amount
            records.append(
                ProfitAllocation(
                    id=generate_snowflake_id(),
                    user_id=user_id,
                    settle_source_user_id=source_user_id,
                    rate=rate,
                    profit_amount=profit_amount,
                    order_amount=order_amount,
                    settle_amount=settle_amount,
                    settle_date=settle_date,
                    settle_source=source,
                    order_import_id=order_import_id,
                    created_at=timezone.now(),
                )
            )

        if records:
            ProfitAllocation.objects.bulk_create(records)
            created_count = len(records)

        changed_user_ids = set(existing_amounts.keys()) | set(new_amounts.keys())
        allocation_deltas = {
            user_id: _quantize_amount(
                new_amounts.get(user_id, Decimal("0.00"))
                - existing_amounts.get(user_id, Decimal("0.00"))
            )
            for user_id in changed_user_ids
        }

        _update_wallets(
            allocation_deltas,
            remark_prefix=f"导入批次 {order_import_id} 分润",
        )
        asset_user_count = sum(1 for delta in allocation_deltas.values() if delta != 0)

    return {
        "order_import_id": order_import_id,
        "bill_date_start": bill_days[0] if bill_days else "",
        "bill_date_end": bill_days[-1] if bill_days else "",
        "order_count": total_order_count,
        "summary_count": len(profit_rows),
        "allocation_count": created_count,
        "total_settle_amount": format(_quantize_amount(total_settle_amount), "f"),
        "asset_user_count": asset_user_count,
    }


def run_profit_allocation_with_tracking(
    order_import_id: int,
) -> dict:
    """带运行记录与导入记录状态回写的分润执行入口。"""
    order_import = OrderImport.objects.filter(id=int(order_import_id)).first()
    if not order_import:
        raise ValueError("订单导入记录不存在")

    order_import.profit_task_status = OrderImport.PROFIT_STATUS_RUNNING
    order_import.profit_run_time = timezone.now()
    order_import.profit_error_message = ""
    order_import.profit_summary_count = 0
    order_import.profit_total_amount = Decimal("0.00")
    order_import.save(
        update_fields=[
            "profit_task_status",
            "profit_run_time",
            "profit_error_message",
            "profit_summary_count",
            "profit_total_amount",
        ]
    )

    start_time = timezone.now()
    result = {}
    error_message = None
    try:
        result = run_profit_allocation(order_import_id=order_import.id)
    except Exception as exc:
        error_message = str(exc)
        logger.exception("Profit allocation task failed for import_id=%s", order_import.id)

    duration = int((timezone.now() - start_time).total_seconds() * 1000)
    bill_date_text = _format_bill_date_text(
        result.get("bill_date_start", ""),
        result.get("bill_date_end", ""),
    )

    ProfitTaskRecord.objects.create(
        id=generate_snowflake_id(),
        run_time=timezone.now(),
        duration=duration,
        bill_date=bill_date_text,
        data_scanned=int(result.get("order_count", 0)),
        profit_data_count=int(result.get("allocation_count", 0)),
        error_message=error_message,
        created_at=timezone.now(),
    )

    if error_message:
        order_import.profit_task_status = OrderImport.PROFIT_STATUS_FAILED
        order_import.profit_error_message = error_message
        order_import.profit_run_time = timezone.now()
        order_import.save(
            update_fields=[
                "profit_task_status",
                "profit_error_message",
                "profit_run_time",
                "profit_summary_count",
                "profit_total_amount",
            ]
        )
        return {"order_import_id": int(order_import.id), "message": error_message}

    order_import.profit_task_status = OrderImport.PROFIT_STATUS_SUCCESS
    order_import.profit_run_time = timezone.now()
    order_import.profit_error_message = ""
    order_import.profit_summary_count = int(result.get("summary_count", 0))
    order_import.profit_total_amount = Decimal(str(result.get("total_settle_amount", "0.00")))
    order_import.save(
        update_fields=[
            "profit_task_status",
            "profit_run_time",
            "profit_error_message",
            "profit_summary_count",
            "profit_total_amount",
        ]
    )
    return result


def rollback_profit_allocation_for_import(order_import_id: int) -> dict:
    """删除导入记录时回滚该批次分润并扣减钱包。"""
    order_import_id = int(order_import_id)
    with transaction.atomic():
        existing_amounts = {
            int(row["user_id"]): _quantize_amount(Decimal(row["total_amount"] or 0))
            for row in ProfitAllocation.objects.filter(order_import_id=order_import_id)
            .values("user_id")
            .annotate(total_amount=Sum("settle_amount"))
        }

        deleted_count, _ = ProfitAllocation.objects.filter(
            order_import_id=order_import_id
        ).delete()

        rollback_deltas = {
            user_id: _quantize_amount(Decimal("0.00") - amount)
            for user_id, amount in existing_amounts.items()
            if amount != 0
        }
        _update_wallets(
            rollback_deltas,
            remark_prefix=f"导入批次 {order_import_id} 分润",
        )

    total_amount = sum(existing_amounts.values(), Decimal("0.00"))
    return {
        "deleted_profit_rows": int(deleted_count or 0),
        "rollback_user_count": len(rollback_deltas),
        "rollback_total_amount": format(_quantize_amount(total_amount), "f"),
    }


def start_profit_scheduler():
    """分润定时任务已下线，保留兼容入口。"""
    return
