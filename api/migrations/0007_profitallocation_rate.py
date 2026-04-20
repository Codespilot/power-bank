from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_profitallocation_settle_source_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="profitallocation",
            name="rate",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
    ]
