"""Send a test SMS to verify gateway configuration."""
from django.core.management.base import BaseCommand

from core.services.sms import send_sms


class Command(BaseCommand):
    help = 'Send a test SMS via the configured provider (Sparrow/Twilio)'

    def add_arguments(self, parser):
        parser.add_argument('phone', help='Recipient phone (e.g. 9801234567)')
        parser.add_argument(
            '--message',
            default='Smart OPD: Test SMS — your notification system is working.',
            help='Message body',
        )

    def handle(self, *args, **options):
        phone = options['phone']
        message = options['message']
        result = send_sms(phone, message)
        if result.success:
            self.stdout.write(self.style.SUCCESS(
                f'SMS sent via {result.provider} to {phone}'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'SMS failed: {result.error}\n{result.detail}'
            ))
