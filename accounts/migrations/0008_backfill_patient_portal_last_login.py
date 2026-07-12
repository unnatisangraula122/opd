from django.db import migrations
from django.utils import timezone


def backfill_portal_login(apps, schema_editor):
    """
    Existing patients who already activated a portal password are treated as
    having logged in once (last_login was never set by the old patient auth).
    Walk-ins without a usable password stay new until first portal login.
    """
    User = apps.get_model('accounts', 'User')
    now = timezone.now()
    for user in User.objects.filter(role='patient', last_login__isnull=True).iterator():
        pwd = user.password or ''
        if pwd and not pwd.startswith('!'):
            user.last_login = user.date_joined or now
            user.save(update_fields=['last_login'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_rename_accounts_ap_user_id_6e8f0a_idx_accounts_ap_user_id_8492a1_idx'),
    ]

    operations = [
        migrations.RunPython(backfill_portal_login, noop_reverse),
    ]
