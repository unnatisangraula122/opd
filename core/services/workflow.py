"""
Central appointment workflow — all status transitions go through here.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core import constants as C
from core.models import (
    Consultation,
    LabOrder,
    PharmacyQueueEntry,
    Prescription,
    QueueEntry,
    Token,
)


def display_status(token):
    """Human-readable status used on every dashboard."""
    return C.DISPLAY_STATUS.get(token.status, token.status.replace('_', ' ').title())


def is_active(token):
    return token.status in C.ACTIVE_STATUSES


def resolve_or_create_patient_user(phone, name, age, address=''):
    """Link booking to existing patient by phone — never duplicate."""
    from accounts.models import User

    user = User.objects.filter(phone=phone, role='patient').first()
    if user:
        if name and not user.get_full_name().strip():
            parts = name.split()
            user.first_name = parts[0]
            user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        if age and not user.age:
            user.age = int(age)
        if address and not user.address:
            user.address = address
        if not user.patient_code:
            user.assign_patient_code()
        user.save()
        return user

    parts = name.split()
    user = User.objects.create(
        username=f'pat_{phone}',
        phone=phone,
        role='patient',
        first_name=parts[0] if parts else name,
        last_name=' '.join(parts[1:]) if len(parts) > 1 else '',
        age=int(age) if age else None,
        address=address or '',
    )
    return user


def _mark_queue_done(token):
    if hasattr(token, 'queue_entry'):
        entry = token.queue_entry
        entry.queue_status = 'done'
        entry.served_at = timezone.now()
        if entry.entered_at:
            entry.wait_minutes = int((entry.served_at - entry.entered_at).total_seconds() / 60)
        entry.save()


def _ensure_pharmacy_queue(token, medicine_count=0):
    bill = Decimal(str(max(medicine_count, 1) * 50))
    entry, _ = PharmacyQueueEntry.objects.get_or_create(
        token=token,
        defaults={'total_bill': bill},
    )
    if medicine_count and entry.total_bill == 0:
        entry.total_bill = bill
        entry.save(update_fields=['total_bill'])
    return entry


@transaction.atomic
def complete_consultation(
    token,
    *,
    symptoms='',
    diagnosis='',
    notes='',
    medicines=None,
    lab_tests=None,
    followup_date=None,
):
    """Doctor finishes consult — saves clinical data and routes patient."""
    if token.status != C.CONSULTING:
        raise ValidationError(f'Cannot complete. Current status: {token.status}')

    medicines = medicines or []
    lab_tests = lab_tests or []

    consultation, _ = Consultation.objects.update_or_create(
        token=token,
        defaults={
            'symptoms': symptoms,
            'diagnosis': diagnosis,
            'notes': notes,
            'requires_lab': bool(lab_tests),
            'requires_followup': bool(followup_date),
            'followup_date': followup_date or None,
        },
    )

    Prescription.objects.filter(consultation=consultation).delete()
    for med in medicines:
        Prescription.objects.create(
            consultation=consultation,
            token=token,
            medicine_name=med.get('name', med.get('medicine_name', '')),
            dosage=med.get('dosage', ''),
            frequency=med.get('frequency', med.get('duration', '')),
            duration_days=med.get('duration_days'),
            instructions=med.get('instructions', ''),
        )

    LabOrder.objects.filter(consultation=consultation).delete()
    for test_name in lab_tests:
        LabOrder.objects.create(
            consultation=consultation,
            token=token,
            test_name=test_name,
            status='fee_pending',
        )

    token.consultation_ended_at = timezone.now()
    _mark_queue_done(token)

    has_lab = bool(lab_tests)
    has_rx = bool(medicines)

    if has_lab:
        token.status = C.PENDING_LAB
    elif has_rx:
        token.status = C.PENDING_PHARMACY
        _ensure_pharmacy_queue(token, len(medicines))
    else:
        token.status = C.COMPLETED

    token.save()

    return {
        'requires_lab': has_lab,
        'requires_pharmacy': has_rx,
        'status': token.status,
        'display_status': display_status(token),
    }


@transaction.atomic
def after_lab_report_uploaded(lab_order):
    """After lab completes — route to pharmacy or mark appointment completed."""
    token = lab_order.token
    pending_labs = token.lab_orders.exclude(status='completed').exists()
    if pending_labs:
        return token.status

    has_undispensed_rx = token.prescriptions.filter(dispensed=False).exists()
    if has_undispensed_rx:
        token.status = C.PENDING_PHARMACY
        _ensure_pharmacy_queue(token, token.prescriptions.count())
    else:
        token.status = C.COMPLETED
    token.save()
    return token.status


@transaction.atomic
def pharmacy_mark_ready(entry):
    if entry.status not in (C.PHARMACY_WAITING, C.PHARMACY_DISPENSING):
        raise ValidationError(f'Cannot mark ready from status: {entry.status}')
    entry.status = C.PHARMACY_READY
    entry.save(update_fields=['status'])
    return entry


@transaction.atomic
def expire_unclaimed_for_slot(slot):
    """Mark booked-but-never-checked-in tokens as expired when slot ends."""
    now = timezone.localtime()
    slot_end = timezone.make_aware(
        timezone.datetime.combine(
            slot.date,
            timezone.datetime.strptime(slot.end_time, '%H:%M').time(),
        )
    )
    if now < slot_end:
        return 0

    expired = Token.objects.filter(slot=slot, status=C.BOOKED).update(status=C.EXPIRED)
    return expired


def expire_all_ended_slots():
    """Run for all today's slots that have passed end time."""
    from core.models import ConsultationSlot

    today = timezone.localdate()
    count = 0
    for slot in ConsultationSlot.objects.filter(date=today):
        count += expire_unclaimed_for_slot(slot)
    return count
