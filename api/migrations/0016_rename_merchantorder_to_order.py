from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0015_order_import_profit_fields"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="MerchantOrder",
            new_name="Order",
        ),
        migrations.AlterModelTable(
            name="order",
            table="order",
        ),
    ]
