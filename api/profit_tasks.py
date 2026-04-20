import logging
import os
import threading
import time
from collections import defaultdict
from datetime import date, datetime, time as dt_time, timedelta, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Merchant, MerchantOrder, ProfitAllocation, User, Wallet
from utils.generate_snowflake_id import generate_snowflake_id

logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()
_AMOUNT_QUANT = Decimal("0.01")


def _quantize_amount(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _field_matches(value: int, expr: str, min_value: int, max_value: int) -> bool:
    if expr == "*":
        return True

    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue

        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if step <= 0:
                return False
            if base == "*":
                start, end = min_value, max_value
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                start, end = int(start_text), int(end_text)
            else:
                start, end = int(base), max_value
            if start <= value <= end and (value - start) % step == 0:
                return True
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if int(start_text) <= value <= int(end_text):
                return True
            continue

        if int(part) == value:
            return True

    return False


def _cron_matches(now_local: datetime, cron_expr: str) -> bool:
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("PROFIT_TASK_CRON must contain 5 fields")

    minute_expr, hour_expr, day_expr, month_expr, weekday_expr = parts
    weekday_value = now_local.isoweekday() % 7

    minute_ok = _field_matches(now_local.minute, minute_expr, 0, 59)
    hour_ok = _field_matches(now_local.hour, hour_expr, 0, 23)
    month_ok = _field_matches(now_local.month, month_expr, 1, 12)
    day_ok = _field_matches(now_local.day, day_expr, 1, 31)
    weekday_ok = _field_matches(weekday_value, weekday_expr, 0, 7) or (
        weekday_value == 0 and _field_matches(7, weekday_expr, 0, 7)
    )

    if day_expr != "*" and weekday_expr != "*":
        day_match = day_ok or weekday_ok
    else:
        day_match = day_ok and weekday_ok

    return minute_ok and hour_ok and month_ok and day_match


def _fetch_profit_summary_rows(start_dt: datetime, end_dt: datetime) -> list[dict]:
    """按账单日期汇总商户订单利润，作为分润任务的原始输入。"""
    sql = """
        SELECT
            mch.agent_id,
            COUNT(odr.id) AS order_count,
            COALESCE(SUM(odr.order_amount), 0) AS order_amount,
            COALESCE(SUM(odr.merchant_profit), 0) AS merchant_profit
        FROM merchant_order AS odr
        INNER JOIN merchant AS mch ON odr.merchant_id = mch.id
        WHERE mch.agent_id IS NOT NULL
          AND mch.agent_id > 0
          AND odr.bill_date >= %s
          AND odr.bill_date < %s
        GROUP BY mch.agent_id
    """

    utc_start = start_dt.astimezone(dt_timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    utc_end = end_dt.astimezone(dt_timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

    with connection.cursor() as cursor:
        cursor.execute(sql, [utc_start, utc_end])
        rows = cursor.fetchall()

    return [
        {
            "agent_id": int(agent_id),
            "order_count": int(order_count or 0),
            "order_amount": _quantize_amount(Decimal(order_amount or 0)),
            "merchant_profit": _quantize_amount(Decimal(merchant_profit or 0)),
        }
        for agent_id, order_count, order_amount, merchant_profit in rows
        if agent_id
    ]


def _get_superior_chain(agent_id: int) -> list[User]:
    """从当前代理开始向上追溯直属上级链路。"""
    chain: list[User] = []
    visited: set[int] = set()
    current_id = int(agent_id)
    cycle_detected = False

    while current_id:
        if current_id in visited:
            cycle_detected = True
            break
        visited.add(current_id)

        current_user = User.objects.only("id", "agent_id", "agent_rate").filter(id=current_id).first()
        if not current_user:
            break
        chain.append(current_user)
        if not current_user.agent_id:
            break
        current_id = int(current_user.agent_id)

    if cycle_detected:
        logger.warning("Detected cycle while loading superior chain for user %s", agent_id)

    return chain


def _allocate_agent_profit(
    agent_id: int,
    total_profit: Decimal,
    total_order_amount: Decimal,
    allocations: dict[tuple[int, str, int | None, Decimal | None], dict[str, Decimal | None]],
):
    """按代理链逐级拆分利润。

    当前级先保留自己的部分，再按 agent_rate 将上级应得金额继续向上递推。
    """
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
        key = (agent.id, current_source, current_source_user_id, current_rate)
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
        current_source_user_id = agent.id
        current_rate = rate


def _update_wallets(allocation_deltas: dict[int, Decimal]):
    """根据当日分润差额增量更新钱包，保证重复执行不会重复入账。"""
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
        wallet.total_amount = _quantize_amount(Decimal(wallet.total_amount or 0) + amount)
        wallet.available_amount = _quantize_amount(Decimal(wallet.available_amount or 0) + amount)
        wallet.save(update_fields=["total_amount", "available_amount"])


def run_profit_allocation(target_date: date | None = None) -> dict:
    print(f"Starting profit allocation task for target date: {target_date}")
    if target_date is None and settings.DEBUG:
        target_date = date(2026, 2, 1)
    else:
        target_date = target_date or (timezone.localdate() - timedelta(days=1))
    start_dt = timezone.make_aware(datetime.combine(target_date, dt_time.min))
    end_dt = start_dt + timedelta(days=1)

    profit_rows = _fetch_profit_summary_rows(start_dt, end_dt)
    if not profit_rows:
        result = {
            "target_date": target_date.isoformat(),
            "order_count": 0,
            "agent_count": 0,
            "allocation_count": 0,
        }
        logger.info("Profit allocation task finished with no eligible orders: %s", result)
        return result

    allocations: dict[tuple[int, str, int | None, Decimal | None], dict[str, Decimal | None]] = defaultdict(
        lambda: {
            "settle_amount": Decimal("0.00"),
            "profit_amount": Decimal("0.00"),
            "order_amount": Decimal("0.00"),
        }
    )
    total_order_count = sum(row["order_count"] for row in profit_rows)

    for row in profit_rows:
        _allocate_agent_profit(row["agent_id"], row["merchant_profit"], row["order_amount"], allocations)

    created_count = 0
    asset_user_count = 0
    with transaction.atomic():
        # 结算逻辑采用“先统计旧值 -> 删除旧记录 -> 重建新记录 -> 按差额更新钱包”，
        # 这样任务重复执行时仍然是幂等的。
        existing_amounts = {
            int(row["user_id"]): _quantize_amount(Decimal(row["total_amount"] or 0))
            for row in ProfitAllocation.objects.filter(settle_date__gte=start_dt, settle_date__lt=end_dt)
            .values("user_id")
            .annotate(total_amount=Sum("settle_amount"))
        }

        ProfitAllocation.objects.filter(settle_date__gte=start_dt, settle_date__lt=end_dt).delete()

        records = []
        new_amounts: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for (user_id, source, source_user_id, rate), payload in allocations.items():
            settle_amount = _quantize_amount(Decimal(payload["settle_amount"] or 0))
            profit_amount = _quantize_amount(Decimal(payload["profit_amount"] or 0))
            order_amount = _quantize_amount(Decimal(payload["order_amount"] or 0))
            if settle_amount <= 0:
                continue
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
                    settle_date=start_dt,
                    settle_source=source,
                    created_at=timezone.now(),
                )
            )

        if records:
            ProfitAllocation.objects.bulk_create(records)
            created_count = len(records)

        changed_user_ids = set(existing_amounts.keys()) | set(new_amounts.keys())
        allocation_deltas = {
            user_id: _quantize_amount(new_amounts.get(user_id, Decimal("0.00")) - existing_amounts.get(user_id, Decimal("0.00")))
            for user_id in changed_user_ids
        }
        _update_wallets(allocation_deltas)
        asset_user_count = sum(1 for delta in allocation_deltas.values() if delta != 0)

    result = {
        "target_date": target_date.isoformat(),
        "order_count": total_order_count,
        "agent_count": len(profit_rows),
        "allocation_count": created_count,
        "asset_user_count": asset_user_count,
    }
    logger.info("Profit allocation task finished: %s", result)
    return result


def _scheduler_loop(cron_expr: str):
    last_run_key = None
    while True:
        try:
            now_local = timezone.localtime()
            run_key = now_local.strftime("%Y-%m-%d %H:%M")
            if run_key != last_run_key and _cron_matches(now_local, cron_expr):
                logger.info("Profit allocation scheduler triggered at %s with cron %s", run_key, cron_expr)
                run_profit_allocation()
                last_run_key = run_key
            time.sleep(20)
        except Exception:
            logger.exception("Profit allocation scheduler execution failed")
            time.sleep(60)


def start_profit_scheduler():
    global _scheduler_started

    cron_expr = os.getenv("PROFIT_TASK_CRON", "").strip()
    if not cron_expr:
        return

    if settings.DEBUG and os.environ.get("RUN_MAIN") != "true":
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        try:
            _cron_matches(timezone.localtime(), cron_expr)
        except ValueError:
            logger.exception("Invalid PROFIT_TASK_CRON value: %s", cron_expr)
            return

        worker = threading.Thread(
            target=_scheduler_loop,
            args=(cron_expr,),
            name="profit-allocation-scheduler",
            daemon=True,
        )
        worker.start()
        _scheduler_started = True
        logger.info("Profit allocation scheduler started with cron %s", cron_expr)
