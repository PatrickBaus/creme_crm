# Generated by Django 4.2 on 2023-04-05 13:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('creme_core', '0120_v2_5__historyline_hline__entity_detailview'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='cremeentity',
            new_name='core__entity__basic_count',
            old_fields=('entity_type', 'is_deleted'),
        ),
    ]
