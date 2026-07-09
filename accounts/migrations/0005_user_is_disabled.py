from django.db import migrations, models


def copy_disabled_from_tokens(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Token = apps.get_model('core', 'Token')
    for user in User.objects.filter(role='patient', is_disabled=False):
        if Token.objects.filter(patient_id=user.pk, is_disabled=True).exists():
            user.is_disabled = True
            user.save(update_fields=['is_disabled'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_pat_patient_code_format'),
        ('core', '0012_laborder_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_disabled',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_disabled_from_tokens, migrations.RunPython.noop),
    ]
