"""SMS notification service — live delivery via Sparrow/Twilio; console only when SMS_DEBUG=True."""
import logging

from django.conf import settings

from core.services.sms_gateway import SmsDeliveryResult, deliver_sms, normalize_nepal_phone

logger = logging.getLogger('opd.sms')


def send_sms(phone: str, message: str) -> SmsDeliveryResult:
    """Send SMS to phone number."""
    phone = (phone or '').strip()
    if not phone:
        return SmsDeliveryResult(success=False, error='Phone number is empty')

    if getattr(settings, 'SMS_DEBUG', False):
        logger.info('SMS_DEBUG to %s: %s', phone, message)
        print(f'\n[SMS DEBUG -> {phone}]\n{message}\n')
        return SmsDeliveryResult(success=True, provider='debug', detail='SMS_DEBUG mode — not sent to phone')

    result = deliver_sms(phone, message)
    if result.success:
        logger.info('SMS sent via %s to %s', result.provider, normalize_nepal_phone(phone))
    else:
        logger.error('SMS failed to %s via %s: %s %s', phone, result.provider, result.error, result.detail)
    return result


def sms_patient_registration(patient_code: str, phone: str) -> SmsDeliveryResult:
    message = (
        f"Welcome to Smart OPD System.\n"
        f"Your Patient ID is {patient_code}.\n"
        f"Please keep this ID for future visits, token booking and logging in in your dashboard."
    )
    return send_sms(phone, message)


def sms_token_booking(token_number: str, estimated_time: str, phone: str, slot_start: str) -> SmsDeliveryResult:
    message = (
        f"Smart OPD: Your token is {token_number}.\n"
        f"Estimated consultation time: around {estimated_time}.\n"
        f"Please arrive at reception at least 15 minutes earlier (before check-in opens) "
        f"for check-in and registration.\n"
        f"Note: Estimated time is approximate and not guaranteed."
    )
    return send_sms(phone, message)


def sms_otp(phone: str, otp_code: str, purpose: str = 'verification') -> SmsDeliveryResult:
    message = f"Smart OPD: Your OTP for {purpose} is {otp_code}. Valid for 5 minutes. Do not share."
    return send_sms(phone, message)


def sms_lab_report_ready(patient_name: str, test_name: str, phone: str) -> SmsDeliveryResult:
    message = (
        f"Smart OPD: Lab report for {test_name} is ready, {patient_name}. "
        f"Please visit reception or check your patient dashboard."
    )
    return send_sms(phone, message)


def sms_followup_reminder(patient_name: str, followup_date: str, phone: str) -> SmsDeliveryResult:
    message = (
        f"Smart OPD Reminder: Dear {patient_name}, you have a follow-up appointment "
        f"scheduled on {followup_date}. Please book your token in advance."
    )
    return send_sms(phone, message)
