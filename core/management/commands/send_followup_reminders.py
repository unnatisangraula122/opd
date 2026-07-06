from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Consultation
from core.services.sms import sms_followup_reminder


class Command(BaseCommand):
    help = 'Send SMS reminders for follow-up appointments scheduled tomorrow'

    def handle(self, *args, **options):
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        consultations = Consultation.objects.filter(
            requires_followup=True,
            followup_date=tomorrow,
        ).select_related('token')

        sent = 0
        failed = 0
        for consult in consultations:
            token = consult.token
            if token.patient_phone:
                result = sms_followup_reminder(
                    token.patient_name,
                    tomorrow.strftime('%d %b %Y'),
                    token.patient_phone,
                )
                if result.success:
                    sent += 1
                else:
                    failed += 1
                    self.stderr.write(f'  Failed {token.patient_phone}: {result.error}')

        self.stdout.write(self.style.SUCCESS(
            f'Sent {sent} follow-up reminder(s) for {tomorrow}' + (f', {failed} failed' if failed else '')
        ))
