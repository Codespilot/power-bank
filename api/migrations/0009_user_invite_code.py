import secrets
import string

from django.db import migrations, models


ALPHABET = string.ascii_lowercase + string.digits


def _generate_code(UserModel):
    while True:
        code = ''.join(secrets.choice(ALPHABET) for _ in range(8))
        if not UserModel.objects.filter(invite_code=code).exists():
            return code


def fill_invite_codes(apps, schema_editor):
    User = apps.get_model('api', 'User')
    for user in User.objects.filter(invite_code__isnull=True):
        user.invite_code = _generate_code(User)
        user.save(update_fields=['invite_code'])


def clear_invite_codes(apps, schema_editor):
    User = apps.get_model('api', 'User')
    User.objects.update(invite_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_profitallocation_totals'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='invite_code',
            field=models.CharField(blank=True, max_length=8, null=True, unique=True),
        ),
        migrations.RunPython(fill_invite_codes, clear_invite_codes),
    ]
