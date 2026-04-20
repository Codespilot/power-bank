from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0011_rename_userasset_wallet"),
    ]

    operations = [
        migrations.CreateModel(
            name="WalletRecord",
            fields=[
                ("id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("before_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("after_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("remark", models.CharField(blank=True, max_length=500, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallet_records",
                        to="api.user",
                    ),
                ),
            ],
            options={
                "db_table": "wallet_record",
                "app_label": "api",
            },
        ),
    ]
