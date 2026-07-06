from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_one_doctor_per_daily_slot'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='consultationslot',
            unique_together={('date', 'slot_type')},
        ),
    ]
