from django.db import migrations, models


def forwards_convert_patient_codes(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    PatientSerial = apps.get_model('accounts', 'PatientSerial')
    max_num = 0
    for user in User.objects.filter(role='patient').exclude(patient_code='').exclude(patient_code__isnull=True):
        code = (user.patient_code or '').strip().upper()
        num = None
        if code.startswith('PAT') and code[3:].isdigit():
            num = int(code[3:])
        elif code.startswith('P') and code[1:].isdigit():
            num = int(code[1:])
            user.patient_code = f'PAT{num:04d}'
            user.save(update_fields=['patient_code'])
        if num is not None:
            max_num = max(max_num, num)
    if max_num:
        seq, _ = PatientSerial.objects.get_or_create(pk=1)
        if seq.last_serial < max_num:
            seq.last_serial = max_num
            seq.save(update_fields=['last_serial'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_patientserial_user_patient_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='patient_code',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
        migrations.RunPython(forwards_convert_patient_codes, migrations.RunPython.noop),
    ]
