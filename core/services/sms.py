"""SMS notification service. Logs to console in dev; swap send() for a real gateway in production."""
import logging
from django.conf import settings

logger = logging.getLogger('opd.sms')


def send_sms(phone: str, message: str) -> bool:
    """Send SMS to phone number. Returns True on success."""
    phone = (phone or '').strip()
    if not phone:
        return False

    # Dev mode: log SMS content (never hardcode OTP in messages from callers)
    if getattr(settings, 'SMS_DEBUG', True):
        logger.info('SMS to %s: %s', phone, message)
        print(f'\n[SMS → {phone}]\n{message}\n')
        return True

    # Production: integrate Twilio / Sparrow SMS / etc.
    api_key = getattr(settings, 'SMS_API_KEY', '')
    if not api_key:
        logger.warning('SMS_API_KEY not configured; message not sent to %s', phone)
        return False

    # Placeholder for real gateway integration
    logger.info('SMS sent to %s via gateway', phone)
    return True


def sms_patient_registration(patient_code: str, phone: str) -> bool:
    message = (
        f"Welcome to Smart OPD System.\n"
        f"Your Patient ID is {patient_code}.\n"
        f"Please keep this ID for future visits, token booking and logging in in your dashboard."
    )
    return send_sms(phone, message)


def sms_token_booking(token_number: str, estimated_time: str, phone: str, slot_start: str) -> bool:
    message = (
        f"Smart OPD: Your token is {token_number}.\n"
        f"Estimated consultation time: around {estimated_time}.\n"
        f"Please arrive at reception at least 15 minutes earlier (before check-in opens) "
        f"for check-in and registration.\n"
        f"Note: Estimated time is approximate and not guaranteed."
    )
    return send_sms(phone, message)


def sms_otp(phone: str, otp_code: str, purpose: str = 'verification') -> bool:
    message = f"Smart OPD: Your OTP for {purpose} is {otp_code}. Valid for 5 minutes. Do not share."
    return send_sms(phone, message)


def sms_lab_report_ready(patient_name: str, test_name: str, phone: str) -> bool:
    message = (
        f"Smart OPD: Lab report for {test_name} is ready, {patient_name}. "
        f"Please visit reception or check your patient dashboard."
    )
    return send_sms(phone, message)


def sms_followup_reminder(patient_name: str, followup_date: str, phone: str) -> bool:
    message = (
        f"Smart OPD Reminder: Dear {patient_name}, you have a follow-up appointment "
        f"scheduled on {followup_date}. Please book your token in advance."
    )
    return send_sms(phone, message)
