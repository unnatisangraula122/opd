# ========== COMBINED API VIEWS ==========
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import models
from django.utils import timezone
from datetime import timedelta
from .models import ConsultationSlot, Token


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'message': 'Smart OPD API is running'})


# ========== MEMBER A: BOOKING API ==========

@api_view(['GET'])
def available_slots(request):
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    slots = ConsultationSlot.objects.filter(date__in=[today, tomorrow])

    available_slots_list = []
    for slot in slots:
        tokens_left = slot.max_tokens - slot.tokens_booked
        if tokens_left > 0:
            available_slots_list.append({
                'slot_id': slot.id,
                'doctor_name': str(slot.doctor),
                'doctor_id': slot.doctor.id,
                'date': slot.date,
                'slot_type': slot.slot_type,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'tokens_available': tokens_left,
                'max_tokens': slot.max_tokens
            })

    return Response({
        'success': True,
        'count': len(available_slots_list),
        'slots': available_slots_list
    })


@api_view(['POST'])
def book_token(request):
    slot_id = request.data.get('slot_id')
    patient_name = request.data.get('patient_name')
    patient_age = request.data.get('patient_age')
    patient_phone = request.data.get('patient_phone')

    if not all([slot_id, patient_name, patient_age, patient_phone]):
        return Response({
            'success': False,
            'error': 'Missing required fields'
        }, status=400)

    try:
        patient_age = int(patient_age)
        if patient_age < 0 or patient_age > 120:
            raise ValueError()
    except ValueError:
        return Response({
            'success': False,
            'error': 'Patient age must be between 0 and 120'
        }, status=400)

    try:
        slot = ConsultationSlot.objects.get(id=slot_id)
    except ConsultationSlot.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Slot not found'
        }, status=404)

    if slot.is_full:
        return Response({
            'success': False,
            'error': f'Slot is full! Maximum capacity is {slot.max_tokens}.'
        }, status=400)

    token = Token.objects.create(
        slot=slot,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_phone=patient_phone
    )

    return Response({
        'success': True,
        'message': 'Token booked successfully!',
        'token': {
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'estimated_time': token.estimated_time.strftime("%I:%M %p"),
            'status': token.status,
            'is_elderly': token.is_elderly
        }
    })