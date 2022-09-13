from uuid import uuid4

from django.db import migrations


def generate_UUIDs(apps, schema_editor):
    for instance in apps.get_model('events', 'EventType').objects.all():
        instance.uuid = uuid4()
        instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005__v2_4__minion_type01'),
    ]

    operations = [
        migrations.RunPython(generate_UUIDs),
    ]
