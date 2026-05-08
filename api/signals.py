from django.utils import timezone

from blinker import signal

from utils.generate_snowflake_id import generate_snowflake_id
from .models import InviteCode, User
import logging
import threading

from api.profit.profit_tasks import run_profit_allocation_with_tracking

logger = logging.getLogger(__name__)
semaphore = threading.Semaphore(1)

order_import_completed = signal("order_import_completed")
@order_import_completed.connect
def handle_order_import_completed(sender, **kwargs):
    """处理订单导入完成的信号，触发利润分配任务"""
    try:
        order_import_id = kwargs.get("order_import_id")
        logger.info(f"订单导入完成，触发利润分配，order_import_id={order_import_id}")

        with semaphore:
            result = run_profit_allocation_with_tracking(int(order_import_id))
            logger.info(f"利润分配完成，order_import_id={order_import_id}, result={result}")
    except Exception as exc:
        logger.error(f"Error in order_import_completed handler: {exc}", exc_info=True)


profit_allocation_completed = signal("profit_allocation_completed")
@profit_allocation_completed.connect
def handle_profit_allocation_completed(sender, **kwargs):
    order_import_id = kwargs.get("order_import_id")
    logger.info(f"利润分配完成，触发后续处理，order_import_id={order_import_id}")
    # 在这里执行利润分配完成后的后续处理逻辑，例如更新统计数据、发送通知等

user_registered = signal("user_registered")
@user_registered.connect
def handle_user_registered(sender, **kwargs):
    user_id = kwargs.get("user_id")
    InviteCode.objects.create(
            id=generate_snowflake_id(),
            user_id=user_id,
            rate=0,
            register_count=0,
            is_valid=True,
            created_at=timezone.now(),
        )
