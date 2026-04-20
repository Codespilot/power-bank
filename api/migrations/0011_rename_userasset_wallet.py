from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_alter_user_invite_code_invitecode'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UserAsset',
            new_name='Wallet',
        ),
        migrations.AlterModelTable(
            name='wallet',
            table='wallet',
        ),
    ]
