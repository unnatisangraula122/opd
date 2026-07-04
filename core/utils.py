from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from .models import DoctorProfile, ConsultationSlot, Token


CONSULTATION_BASE_FEE = Decimal('660.00')
SERVICE_CHARGE_RATE = Decimal('0.015')


def slot_type_display(slot_type):
    return slot_type.upper() if slot_type else ''


def slot_time_range(slot_type):
    ranges = {
        'morning': '9:00 - 11:00',
        'afternoon': '12:00 - 2:00',
        'evening': '3:00 - 5:00',
    }
    return ranges.get(slot_type, '')


def serialize_slot(slot):
    tokens_left = slot.max_tokens - slot.tokens_booked
    doctor = slot.doctor
    fee = float(CONSULTATION_BASE_FEE)
    return {
        'slot_id': slot.id,
        'doctor_id': doctor.id,
        'doctor_name': str(doctor),
        'specialization': doctor.specialization,
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
        'patient_address': token.patient_address,
        'status': token.status,
        'checkin_status': token.checkin_status,
        'estimated_time': token.estimated_time.strftime('%I:%M %p') if token.estimated_time else None,
        'doctor_name': str(token.slot.doctor),
        'doctor_id': token.slot.doctor_id,
        'date': token.slot.date.isoformat(),
        'slot_type': slot_type_display(token.slot.slot_type),
        'slot_type_raw': token.slot.slot_type,
        'is_elderly': token.is_elderly,
        'is_disabled': token.is_disabled,
        'is_followup': token.is_followup,
        'fee_exempted': token.fee_exempted,
        'checked_in_at': token.checked_in_at.strftime('%I:%M %p') if token.checked_in_at else None,
    }
    if token.patient_id:
        data['patient_user_id'] = token.patient_id
    if include_queue and hasattr(token, 'queue_entry'):
        data['queue_position'] = token.queue_entry.queue_position
        data['priority'] = token.queue_entry.priority
    return data


def ensure_today_tomorrow_slots():
    """Create consultation slots for all doctors for today and tomorrow."""
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    slot_types = ['morning', 'afternoon', 'evening']
    for doctor in DoctorProfile.objects.filter(is_available=True):
        for day in (today, tomorrow):
            for slot_type in slot_types:
                ConsultationSlot.objects.get_or_create(
                    doctor=doctor,
                    date=day,
                    slot_type=slot_type,
                )


def get_doctor_for_user(user):
    if user.role != 'doctor':
        return None
    return DoctorProfile.objects.filter(user=user).first()


def consultation_fee_with_charge(base_fee=None):
    base = base_fee or CONSULTATION_BASE_FEE
    service = (base * SERVICE_CHARGE_RATE).quantize(Decimal('0.01'))
    return base, service, base + service
