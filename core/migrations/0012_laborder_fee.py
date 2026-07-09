from decimal import Decimal

from django.db import migrations, models

from core.services.lab_catalog import get_lab_fee


def backfill_lab_order_fees(apps, schema_editor):
    LabOrder = apps.get_model('core', 'LabOrder')
    for order in LabOrder.objects.all().iterator():
        order.fee = get_lab_fee(order.test_name)
        order.save(update_fields=['fee'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_slottypeconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='laborder',
            name='fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('500'), max_digits=10),
        ),
        migrations.RunPython(backfill_lab_order_fees, migrations.RunPython.noop),
    ]
