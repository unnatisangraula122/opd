"""OTP generation, storage, and verification."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from core.models import OTPVerification
from core.services.sms import sms_otp

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_otp() -> str:
    if getattr(settings, 'SMS_DEBUG', False):
        dummy = getattr(settings, 'SMS_DUMMY_OTP', '123456')
        if len(dummy) == OTP_LENGTH and dummy.isdigit():
            return dummy
    return ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))


def send_otp(phone: str, purpose: str) -> dict:
    """Create and send OTP. Returns {success, message, expires_in}."""
    phone = phone.strip()
    if len(phone) < 10:
        return {'success': False, 'error': 'Invalid phone number'}

    if purpose in ('login', 'password_reset'):
        if not User.objects.filter(phone=phone, role='patient').exists():
            return {
                'success': False,
                'error': 'No patient account for this phone. Use Patient ID login or register at reception first.',
            }

    if purpose == 'registration':
        existing = User.objects.filter(phone=phone, role='patient').first()
        if existing and existing.has_usable_password():
            return {
                'success': False,
                'error': 'An online account already exists for this phone. Please use Old Patient login.',
                'already_registered': True,
            }

    recent = OTPVerification.objects.filter(
        phone=phone,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=RESEND_COOLDOWN_SECONDS),
        is_verified=False,
    ).first()
    if recent:
        wait = RESEND_COOLDOWN_SECONDS - int((timezone.now() - recent.created_at).total_seconds())
        return {'success': False, 'error': f'Please wait {max(wait, 1)} seconds before resending OTP'}

    # Invalidate previous unverified OTPs for same phone/purpose
    OTPVerification.objects.filter(phone=phone, purpose=purpose, is_verified=False).update(
        expires_at=timezone.now()
    )

    code = generate_otp()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    otp_record = OTPVerification.objects.create(
        phone=phone,
        otp_hash=_hash_otp(code),
        purpose=purpose,
        expires_at=expires_at,
    )

    purpose_label = purpose.replace('_', ' ')
    sms_result = sms_otp(phone, code, purpose_label)

    if not sms_result.success:
        otp_record.delete()
        return {
            'success': False,
            'error': sms_result.error or 'Failed to send OTP SMS. Check SMS gateway configuration.',
        }

    result = {
        'success': True,
        'message': f'OTP sent to {phone}',
        'expires_in': OTP_EXPIRY_MINUTES * 60,
        'otp_id': otp_record.id,
    }
    if getattr(settings, 'SMS_DEBUG', False):
        result['dev_mode'] = True
        result['dev_otp'] = code
        result['message'] = f'Dummy OTP mode — use {code} (not sent to phone).'
    return result


def verify_otp(phone: str, otp: str, purpose: str) -> dict:
    """Verify OTP. Returns {success, verified_token} on success."""
    phone = phone.strip()
    otp = (otp or '').strip()

    if len(otp) != OTP_LENGTH or not otp.isdigit():
        return {'success': False, 'error': 'Invalid OTP format'}

    record = OTPVerification.objects.filter(
        phone=phone,
        purpose=purpose,
        is_verified=False,
    ).order_by('-created_at').first()

    if not record:
        return {'success': False, 'error': 'No OTP found. Please request a new one.'}

    if timezone.now() > record.expires_at:
        return {'success': False, 'error': 'OTP has expired. Please request a new one.'}

    if record.attempts >= record.max_attempts:
        return {'success': False, 'error': 'Maximum retry attempts exceeded. Request a new OTP.'}

    record.attempts += 1
    record.save(update_fields=['attempts'])

    if _hash_otp(otp) != record.otp_hash:
        remaining = record.max_attempts - record.attempts
        if remaining <= 0:
            return {'success': False, 'error': 'Maximum retry attempts exceeded. Request a new OTP.'}
        return {'success': False, 'error': f'Invalid OTP. {remaining} attempt(s) remaining.'}

    record.is_verified = True
    record.verified_at = timezone.now()
    record.save(update_fields=['is_verified', 'verified_at'])

    return {
        'success': True,
        'message': 'OTP verified successfully',
        'verified_token': str(record.id),
    }


def is_otp_verified(phone: str, purpose: str, within_minutes: int = 10) -> bool:
    """Check if phone has a recently verified OTP for purpose."""
    cutoff = timezone.now() - timedelta(minutes=within_minutes)
    return OTPVerification.objects.filter(
        phone=phone,
        purpose=purpose,
        is_verified=True,
        verified_at__gte=cutoff,
    ).exists()
