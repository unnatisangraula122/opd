from django.core.management.base import BaseCommand

from core.services.workflow import expire_all_ended_slots


class Command(BaseCommand):
    help = (
        'After slot end: mark unclaimed bookings as no-show. '
        'Patients already checked in or consulting are left in queue.'
    )

    def handle(self, *args, **options):
        count = expire_all_ended_slots()
        self.stdout.write(self.style.SUCCESS(
            f'Marked {count} unclaimed booking(s) as no-show for ended slots'
        ))
