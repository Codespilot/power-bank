from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def migrate_agent_relation_to_user(apps, schema_editor):
    User = apps.get_model("api", "User")
    Agent = apps.get_model("api", "Agent")

    latest_relations = {}
    for relation in Agent.objects.all().order_by("subordinate_id", "-created_at", "-id"):
        if relation.subordinate_id not in latest_relations:
            latest_relations[relation.subordinate_id] = relation

    for subordinate_id, relation in latest_relations.items():
        User.objects.filter(id=subordinate_id).update(
            agent_id=relation.superior_id,
            agent_rate=relation.rate if relation.rate is not None else Decimal("0.00"),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_merchantorder_order_no"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                db_column="agent_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subordinates",
                to="api.user",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="agent_rate",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.RunPython(migrate_agent_relation_to_user, migrations.RunPython.noop),
    ]
