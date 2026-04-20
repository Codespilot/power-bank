from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_profitallocation_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="profitallocation",
            name="order_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="profitallocation",
            name="profit_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
    ]
