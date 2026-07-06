# Consolidate duplicate slots before unique constraint

from django.db import migrations
from django.db.models import Count


def consolidate_duplicate_slots(apps, schema_editor):
    ConsultationSlot = apps.get_model('core', 'ConsultationSlot')
    Token = apps.get_model('core', 'Token')
    seen = {}
    for slot in ConsultationSlot.objects.annotate(token_count=Count('tokens')).order_by('date', 'slot_type', '-token_count'):
        key = (slot.date, slot.slot_type)
        if key not in seen:
            seen[key] = slot.id
            continue
        Token.objects.filter(slot_id=slot.id).update(slot_id=seen[key])
        ConsultationSlot.objects.filter(pk=slot.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_merge_20260705_2108'),
    ]

    operations = [
        migrations.RunPython(consolidate_duplicate_slots, migrations.RunPython.noop),
    ]
