import threading
import pandas as pd
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from .models import OrderImport, Order, Merchant
from config.import_map import get_import_column_mapping
from utils.generate_snowflake_id import generate_snowflake_id
import warnings
from blinker import signal

warnings.filterwarnings("ignore", message="DateTimeField .* received a naive datetime.*while time zone support is active.", category=RuntimeWarning)


def process_imported_excel(order_import_id, file_path):
    import traceback
    import os

    log_dir = os.path.join(os.path.dirname(file_path), "import_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"import_{order_import_id}.log")

    def log(msg):
        print(msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    try:
        order_import = OrderImport.objects.get(id=order_import_id)
        column_mapping = get_import_column_mapping()
        df = pd.read_excel(file_path)
        df.rename(columns=column_mapping, inplace=True)

        orders_to_create: list[Order] = []
        merchant_ids: set[int] = set()
        merchant_names: dict[int, str] = {}
        succeed, failed = 0, 0

        for idx, row in df.iterrows():
            try:
                order_date = (
                    str(row.get("order_date"))
                    if row.get("order_date") is not None
                    else None
                )
                bill_month = (
                    str(row.get("bill_month"))
                    if row.get("bill_month") is not None
                    else None
                )
                bill_date = (
                    str(row.get("bill_date"))
                    if row.get("bill_date") is not None
                    else None
                )

                agent_profit = row.get("agent_profit")
                if agent_profit is None or (
                    isinstance(agent_profit, float) and pd.isna(agent_profit)
                ):
                    agent_profit = 0
                try:
                    agent_profit = Decimal(str(agent_profit))
                except (InvalidOperation, ValueError, TypeError):
                    agent_profit = Decimal("0")

                merchant_profit = row.get("merchant_profit")
                if merchant_profit is None or (
                    isinstance(merchant_profit, float) and pd.isna(merchant_profit)
                ):
                    merchant_profit = 0
                try:
                    merchant_profit = Decimal(str(merchant_profit))
                except (InvalidOperation, ValueError, TypeError):
                    merchant_profit = Decimal("0")

                merchant_id = row.get("merchant_id")
                try:
                    merchant_id = int(merchant_id)
                except (TypeError, ValueError):
                    merchant_id = 0

                orders_to_create.append(
                    Order(
                        id=generate_snowflake_id(),
                        import_id=order_import_id,
                        order_no=row.get("order_no"),
                        order_date=order_date,
                        bill_month=bill_month,
                        bill_date=bill_date,
                        order_type=row.get("order_type"),
                        order_amount=row.get("order_amount"),
                        merchant_name=row.get("merchant_name"),
                        merchant_id=merchant_id,
                        merchant_profit=merchant_profit,
                        agent_profit=agent_profit,
                        created_at=timezone.now(),
                    )
                )

                if merchant_id > 0:
                    merchant_ids.add(merchant_id)
                    merchant_names.setdefault(
                        merchant_id, row.get("merchant_name") or ""
                    )

                succeed += 1

            except Exception as row_exc:
                failed += 1
                log(f"Row {idx+1} failed: {row_exc}\n{traceback.format_exc()}")

        # 先确保商户存在，才能通过商户匹配 agent
        if merchant_ids:
            existing_merchant_ids = set(
                Merchant.objects.filter(id__in=list(merchant_ids))
                .values_list("id", flat=True)
            )
            merchants_to_create = [
                Merchant(
                    id=mid,
                    name=merchant_names[mid],
                    created_at=timezone.now(),
                )
                for mid in merchant_ids
                if mid not in existing_merchant_ids
            ]
            if merchants_to_create:
                Merchant.objects.bulk_create(merchants_to_create, ignore_conflicts=False)

        # 通过商户匹配 agent_id
        merchant_agent_map: dict[int, int] = {}
        if merchant_ids:
            merchants = Merchant.objects.filter(id__in=list(merchant_ids)).exclude(
                agent_id__isnull=True
            ).values_list("id", "agent_id")
            for mid, aid in merchants:
                merchant_agent_map[mid] = aid

        for order in orders_to_create:
            order.agent_id = merchant_agent_map.get(order.merchant_id)

        # 批量插入订单（一次写入，避免逐行 INSERT）
        if orders_to_create:
            Order.objects.bulk_create(orders_to_create, ignore_conflicts=False)
        order_import.succeed_rows = succeed
        order_import.failed_rows = failed
        order_import.status = (
            OrderImport.STATUS_SUCCESS if failed == 0 else OrderImport.STATUS_FAILED
        )
        order_import.save()

        if failed == 0:
            try:
                order_import_completed = signal("order_import_completed")
                order_import_completed.send(None, order_import_id=order_import_id)
            except Exception as profit_exc:
                log(f"Profit task failed for import_id={order_import_id}: {profit_exc}")
    except Exception as e:
        log(f"Import failed: {e}\n{traceback.format_exc()}")
        order_import = OrderImport.objects.get(id=order_import_id)
        order_import.status = OrderImport.STATUS_FAILED
        order_import.save()


def start_import_task(order_import_id, file):
    # 保存上传文件到临时路径
    import os, tempfile

    tmp_dir = tempfile.gettempdir()
    file_path = os.path.join(tmp_dir, f"import_{order_import_id}.xlsx")
    with open(file_path, "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
    t = threading.Thread(
        target=process_imported_excel, args=(order_import_id, file_path)
    )
    t.start()
