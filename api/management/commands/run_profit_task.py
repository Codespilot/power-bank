from django.core.management.base import BaseCommand, CommandError

from api.models import OrderImport
from api.profit.profit_tasks import run_profit_allocation_with_tracking


class Command(BaseCommand):
    help = "Run the profit allocation task for a specified order import record"

    def add_arguments(self, parser):
        parser.add_argument(
            "--order-import-id",
            dest="order_import_id",
            required=False,
            help="Order import id. If omitted, run latest eligible import.",
        )

    def handle(self, *args, **options):
        order_import_id = options.get("order_import_id")
        if order_import_id:
            try:
                order_import_id = int(order_import_id)
            except (TypeError, ValueError) as exc:
                raise CommandError("Invalid --order-import-id") from exc
        else:
            latest = (
                OrderImport.objects.filter(
                    status=OrderImport.STATUS_SUCCESS,
                    failed_rows=0,
                )
                .filter(
                    profit_task_status__in=[
                        OrderImport.PROFIT_STATUS_NOT_STARTED,
                        OrderImport.PROFIT_STATUS_FAILED,
                    ]
                )
                .order_by("-id")
                .first()
            )
            if not latest:
                raise CommandError("No eligible order import record found")
            order_import_id = int(latest.id)

        result = run_profit_allocation_with_tracking(order_import_id=order_import_id)
        self.stdout.write(self.style.SUCCESS(f"Profit task completed: {result}"))
