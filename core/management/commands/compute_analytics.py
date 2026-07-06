from django.core.management.base import BaseCommand
from django.utils import timezone

from core.services.analytics import compute_daily_analytics, compute_kpis, generate_slot_recommendations


class Command(BaseCommand):
    help = 'Compute daily analytics aggregates and slot optimization recommendations'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Date YYYY-MM-DD (default: today)')

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.localdate()

        records = compute_daily_analytics(date)
        self.stdout.write(self.style.SUCCESS(f'Computed analytics for {len(records)} slot(s) on {date}'))

        kpis = compute_kpis(date)
        self.stdout.write(f"  Throughput: {kpis['system_throughput']}, Avg wait: {kpis['avg_waiting_minutes']} min")

        recs = generate_slot_recommendations()
        if recs:
            self.stdout.write(self.style.WARNING(f'Generated {len(recs)} slot optimization recommendation(s)'))
        else:
            self.stdout.write('No new slot optimization recommendations needed.')
