import threading
import pandas as pd
from django.utils import timezone
from .models import OrderImport, MerchantOrder
from config.import_map import get_import_column_mapping
from utils.generate_snowflake_id import generate_snowflake_id
import warnings

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
        order_rows = []
        order_import = OrderImport.objects.get(id=order_import_id)
        column_mapping = get_import_column_mapping()
        df = pd.read_excel(file_path)
        df.rename(columns=column_mapping, inplace=True)
        succeed, failed = 0, 0
        for idx, row in df.iterrows():
            order_rows.append(row)
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
                from decimal import Decimal, InvalidOperation

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

                MerchantOrder.objects.create(
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
                succeed += 1
            except Exception as row_exc:
                failed += 1
                log(f"Row {idx+1} failed: {row_exc}\n{traceback.format_exc()}")

        # 订单导入完成后，批量检查商户
        from .models import Merchant
        merchant_set = set()
        for row in order_rows:
            merchant_id = row.get("merchant_id")
            merchant_name = row.get("merchant_name") or ''
            try:
                merchant_id = int(merchant_id)
            except (TypeError, ValueError):
                merchant_id = 0
            if merchant_id > 0:
                merchant_set.add((merchant_id, merchant_name))

        for merchant_id, merchant_name in merchant_set:
            try:
                merchant_obj = Merchant.objects.filter(id=merchant_id).first()
                if not merchant_obj:
                    Merchant.objects.create(
                        id=merchant_id,
                        name=merchant_name,
                        created_at=timezone.now()
                    )
            except Exception as merchant_exc:
                log(f"Merchant create failed for id={merchant_id}: {merchant_exc}")
        order_import.succeed_rows = succeed
        order_import.failed_rows = failed
        order_import.status = (
            OrderImport.STATUS_SUCCESS if failed == 0 else OrderImport.STATUS_FAILED
        )
        order_import.save()
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
