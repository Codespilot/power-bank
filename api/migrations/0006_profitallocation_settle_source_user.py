from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_user_fullname"),
    ]

    operations = [
        migrations.AddField(
            model_name="profitallocation",
            name="settle_source_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column="settle_source_user_id",
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_profit_allocations",
                to="api.user",
            ),
        ),
    ]
