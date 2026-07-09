from datetime import time

from django.db import migrations, models


def seed_slot_type_configs(apps, schema_editor):
    SlotTypeConfig = apps.get_model('core', 'SlotTypeConfig')
    defaults = {
        'morning': (time(9, 0), time(11, 0), 10, 15),
        'afternoon': (time(12, 0), time(14, 0), 10, 15),
        'evening': (time(15, 0), time(17, 0), 10, 15),
    }
    for slot_type, (start, end, avg, checkin_before) in defaults.items():
        SlotTypeConfig.objects.get_or_create(
            slot_type=slot_type,
            defaults={
                'start_time': start,
                'end_time': end,
                'avg_consultation_minutes': avg,
                'checkin_opens_minutes_before': checkin_before,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_pharmacyqueueentry_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlotTypeConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot_type', models.CharField(choices=[('morning', 'Morning (9:00-11:00)'), ('afternoon', 'Afternoon (12:00-14:00)'), ('evening', 'Evening (15:00-17:00)')], max_length=20, unique=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('avg_consultation_minutes', models.PositiveIntegerField(default=10)),
                ('checkin_opens_minutes_before', models.PositiveIntegerField(default=15)),
            ],
            options={
                'verbose_name': 'Slot type configuration',
                'verbose_name_plural': 'Slot type configurations',
            },
        ),
        migrations.RunPython(seed_slot_type_configs, migrations.RunPython.noop),
    ]
