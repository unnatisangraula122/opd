from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from .models import DoctorProfile, ConsultationSlot, Token

CONSULTATION_BASE_FEE = Decimal('660.00')
SERVICE_CHARGE_RATE = Decimal('0.015')
SLOT_TYPES = ['morning', 'afternoon', 'evening']
ELDERLY_AGE_THRESHOLD = 70
DOCTOR_SPECIALIZATION_LABEL = 'General Physician'


def doctor_display_name(doctor):
    return f"Dr. {doctor.user.get_full_name()} - {DOCTOR_SPECIALIZATION_LABEL}"


def is_elderly_by_age(age):
    try:
        return int(age) >= ELDERLY_AGE_THRESHOLD
    except (TypeError, ValueError):
        return False


def slot_type_display(slot_type):
    return slot_type.upper() if slot_type else ''


def slot_time_range(slot_type):
    ranges = {
        'morning': '9:00 AM - 11:00 AM',
        'afternoon': '12:00 PM - 2:00 PM',
        'evening': '3:00 PM - 5:00 PM',
    }
    return ranges.get(slot_type, '')


def format_local_time(dt, fmt='%I:%M %p'):
    """Format a timezone-aware datetime in the project's local timezone."""
    if not dt:
        return None
    return timezone.localtime(dt).strftime(fmt)


def serialize_slot(slot):
    tokens_left = slot.max_tokens - slot.tokens_booked
    doctor = slot.doctor
    fee = float(CONSULTATION_BASE_FEE)
    return {
        'slot_id': slot.id,
        'doctor_id': doctor.id,
        'doctor_name': f"Dr. {doctor.user.get_full_name()}",
        'specialization': DOCTOR_SPECIALIZATION_LABEL,
        'qualification': doctor.qualification or '',
        'date': slot.date.isoformat(),
        'slot_type': slot.slot_type,
        'slot_type_display': slot_type_display(slot.slot_type),
        'start_time': slot.start_time,
        'end_time': slot.end_time,
        'time_range': slot_time_range(slot.slot_type),
        'tokens_available': max(tokens_left, 0),
        'tokens_booked': slot.tokens_booked,
        'max_tokens': slot.max_tokens,
        'fee': fee,
        'is_full': slot.is_full,
        'is_throttled': doctor.is_throttled,
    }


def serialize_token(token, include_queue=False):
    data = {
        'token_id': token.id,
        'token_number': token.token_number,
        'patient_name': token.patient_name,
        'patient_age': token.patient_age,
        'patient_phone': token.patient_phone,
        'patient_address': token.patient_address or '',
        'status': token.status,
        'checkin_status': token.checkin_status,
        'estimated_time': format_local_time(token.estimated_time),
        'doctor_name': doctor_display_name(token.slot.doctor),
        'doctor_id': token.slot.doctor_id,
        'date': token.slot.date.isoformat(),
        'slot_type': slot_type_display(token.slot.slot_type),
        'slot_type_raw': token.slot.slot_type,
        'start_time': token.slot.start_time,
        'end_time': token.slot.end_time,
        'is_elderly': token.is_elderly,
        'is_disabled': token.is_disabled,
        'is_followup': token.is_followup,
        'fee_exempted': token.fee_exempted,
        'checked_in_at': format_local_time(token.checked_in_at),
    }
    if token.patient_id:
        data['patient_user_id'] = token.patient_id
    patient_user = getattr(token, 'patient', None)
    if patient_user and getattr(patient_user, 'patient_id', None):
        data['patient_id'] = patient_user.patient_id
    if include_queue and hasattr(token, 'queue_entry'):
        data['queue_position'] = token.queue_entry.queue_position
        data['priority'] = token.queue_entry.priority
    return data


def _consolidate_slot_for_day(day, slot_type, assigned_doctor):
    """Ensure exactly one ConsultationSlot per (date, slot_type)."""
    existing = list(ConsultationSlot.objects.filter(date=day, slot_type=slot_type))
    if existing:
        canonical = max(existing, key=lambda s: s.tokens.count())
        for dup in existing:
            if dup.pk != canonical.pk:
                Token.objects.filter(slot=dup).update(slot=canonical)
                dup.delete()
        if canonical.doctor_id != assigned_doctor.id and canonical.tokens.count() == 0:
            canonical.doctor = assigned_doctor
            canonical.save(update_fields=['doctor'])
        return canonical
    return ConsultationSlot.objects.create(
        doctor=assigned_doctor,
        date=day,
        slot_type=slot_type,
    )


def ensure_today_tomorrow_slots():
    """Create 3 slots per day — one doctor per slot (morning/afternoon/evening)."""
    doctors = list(DoctorProfile.objects.filter(is_available=True).order_by('id'))
    if not doctors:
        return

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    for day in (today, tomorrow):
        for idx, slot_type in enumerate(SLOT_TYPES):
            assigned_doctor = doctors[idx % len(doctors)]
            _consolidate_slot_for_day(day, slot_type, assigned_doctor)


def get_daily_slots_for_dates(dates):
    """Return at most one slot per slot_type for each date (after ensure)."""
    ensure_today_tomorrow_slots()
    result = []
    for day in dates:
        for slot_type in SLOT_TYPES:
            slot = ConsultationSlot.objects.filter(
                date=day,
                slot_type=slot_type,
                doctor__is_available=True,
            ).select_related('doctor__user').first()
            if slot:
                result.append(slot)
    return result


def get_doctor_for_user(user):
    if user.role != 'doctor':
        return None
    return DoctorProfile.objects.filter(user=user).first()


def consultation_fee_with_charge(base_fee=None):
    base = base_fee or CONSULTATION_BASE_FEE
    service = (base * SERVICE_CHARGE_RATE).quantize(Decimal('0.01'))
    return base, service, base + service
