from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ConsultationSlot, Token


class Command(BaseCommand):
    help = 'Mark unclaimed booked tokens as expired after their slot ends'

    def handle(self, *args, **options):
        now = timezone.localtime()
        today = now.date()
        expired_count = 0

        slots = ConsultationSlot.objects.filter(date__lte=today)
        for slot in slots:
            slot_end = timezone.make_aware(
                datetime.combine(slot.date, datetime.strptime(slot.end_time, '%H:%M').time())
            )
            if now <= slot_end and slot.date == today:
                continue
            for token in Token.objects.filter(slot=slot, status='booked'):
                token.expire_if_unclaimed()
                expired_count += 1

        self.stdout.write(self.style.SUCCESS(f'Expired {expired_count} unclaimed token(s)'))
