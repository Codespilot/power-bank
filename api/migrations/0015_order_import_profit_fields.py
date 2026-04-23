from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_rename_duration_ms_profittaskrecord_duration_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderimport",
            name="profit_error_message",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderimport",
            name="profit_run_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderimport",
            name="profit_summary_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="orderimport",
            name="profit_task_status",
            field=models.IntegerField(
                choices=[(1, "未运行"), (2, "正在运行"), (3, "完成"), (4, "失败")],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="orderimport",
            name="profit_total_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="profitallocation",
            name="order_import_id",
            field=models.BigIntegerField(db_index=True, default=0),
        ),
    ]
