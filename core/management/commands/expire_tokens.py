from django.core.management.base import BaseCommand

from core.services.workflow import expire_all_ended_slots


class Command(BaseCommand):
    help = (
        'After slot end: mark unclaimed bookings as no-show, and close '
        'stale checked-in / consulting / lab / pharmacy visits as completed'
    )

    def handle(self, *args, **options):
        count = expire_all_ended_slots()
        self.stdout.write(self.style.SUCCESS(
            f'Closed {count} unfinished token(s) for ended slots'
        ))
