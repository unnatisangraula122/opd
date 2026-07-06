from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import (
    Consultation, ConsultationSlot, LabOrder, PharmacyQueueEntry,
    Prescription, Token,
)
from core.permissions import IsDoctor
from core.services.analytics import get_next_eligible_token
from core.utils import get_doctor_for_user, serialize_token


def _queue_for_doctor(doctor_id, slot_type=None, statuses=('checked_in',)):
    today = timezone.localdate()
    doctor_slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    if slot_type:
        doctor_slots = doctor_slots.filter(slot_type=slot_type)
    tokens = Token.objects.filter(
        slot__in=doctor_slots,
        status__in=statuses,
    ).select_related('slot').prefetch_related('queue_entry')

    queue_list = []
    for token in tokens:
        entry = getattr(token, 'queue_entry', None)
        queue_list.append({
            'position': entry.queue_position if entry else len(queue_list) + 1,
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'patient_phone': token.patient_phone,
            'is_elderly': token.is_elderly,
            'is_disabled': token.is_disabled,
            'priority': 'HIGH' if (token.is_elderly or token.is_disabled) else 'NORMAL',
            'status': token.status,
        })

    queue_list.sort(key=lambda x: (x['priority'] != 'HIGH', x['token_number']))
    for idx, patient in enumerate(queue_list):
        patient['position'] = idx + 1
    return queue_list


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctor])
def doctor_schedule(request):
    profile = get_doctor_for_user(request.user)
    if not profile:
        return Response({'success': False, 'error': 'Doctor profile not found'}, status=404)
    today = timezone.localdate()
    slots = ConsultationSlot.objects.filter(doctor=profile, date=today)
    return Response({
        'success': True,
        'doctor': {'id': profile.id, 'name': str(profile), 'specialization': profile.specialization},
        'slots': [{
            'slot_id': s.id,
            'slot_type': s.slot_type,
            'tokens_booked': s.tokens_booked,
            'max_tokens': s.max_tokens,
        } for s in slots],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctor])
def doctor_queue(request, doctor_id=None):
    profile = get_doctor_for_user(request.user)
    if not profile:
        return Response({'success': False, 'error': 'Doctor profile not found'}, status=404)
    if doctor_id and int(doctor_id) != profile.id:
        return Response({'success': False, 'error': 'Access denied'}, status=403)

    queue_list = _queue_for_doctor(profile.id)
    return Response({
        'success': True,
        'doctor_id': profile.id,
        'queue_length': len(queue_list),
        'next_patient': queue_list[0] if queue_list else None,
        'queue': queue_list,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDoctor])
def next_patient(request, doctor_id=None):
    profile = get_doctor_for_user(request.user)
    queue_list = _queue_for_doctor(profile.id)
    if not queue_list:
        return Response({'success': True, 'has_next': False})
    return Response({'success': True, 'has_next': True, 'next_patient': queue_list[0]})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDoctor])
def start_consultation(request, token_id):
    profile = get_doctor_for_user(request.user)
    if not profile:
        return Response({'success': False, 'error': 'Doctor profile not found'}, status=404)

    try:
        token = Token.objects.get(id=token_id, slot__doctor=profile)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)

    next_token = get_next_eligible_token(profile.id)
    if next_token and next_token.id != token.id:
        return Response({
            'success': False,
            'error': (
                f'Queue discipline enforced: call token {next_token.token_number} '
                f'({next_token.patient_name}) first.'
            ),
            'next_patient': {
                'token_id': next_token.id,
                'token_number': next_token.token_number,
                'patient_name': next_token.patient_name,
            },
        }, status=400)

    try:
        token.start_consultation()
    except ValidationError as exc:
        return Response({'success': False, 'error': str(exc)}, status=400)
    return Response({
        'success': True,
        'message': f'Consultation started for {token.patient_name}',
        'token': serialize_token(token),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDoctor])
def complete_consultation(request, token_id):
    try:
        token = Token.objects.get(id=token_id, slot__doctor__user=request.user)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)

    if token.status != 'consulting':
        return Response({'success': False, 'error': f'Cannot complete. Status: {token.status}'}, status=400)

    symptoms = request.data.get('symptoms', '')
    diagnosis = request.data.get('diagnosis', '')
    notes = request.data.get('notes', '')
    medicines = request.data.get('medicines', [])
    lab_tests = request.data.get('lab_tests', [])
    followup_date = request.data.get('followup_date')

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
    if lab_tests:
        token.status = 'pending_lab'
    elif medicines:
        token.status = 'pending_pharmacy'
        PharmacyQueueEntry.objects.get_or_create(
            token=token,
            defaults={'total_bill': len(medicines) * 50},
        )
    else:
        token.status = 'completed'
    token.save()

    if hasattr(token, 'queue_entry'):
        entry = token.queue_entry
        entry.queue_status = 'done'
        entry.served_at = timezone.now()
        if entry.entered_at:
            entry.wait_minutes = int((entry.served_at - entry.entered_at).total_seconds() / 60)
        entry.save()

    duration = None
    if token.consultation_started_at and token.consultation_ended_at:
        duration = round((token.consultation_ended_at - token.consultation_started_at).total_seconds() / 60, 1)

    return Response({
        'success': True,
        'message': f'Consultation completed for {token.patient_name}',
        'token': serialize_token(token),
        'consultation_duration_minutes': duration,
        'requires_lab': bool(lab_tests),
        'requires_pharmacy': bool(medicines),
    })
