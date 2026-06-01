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
    """
    Get all available slots for today and tomorrow
    URL: GET /api/core/slots/
    """
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Get slots for today and tomorrow
    slots = ConsultationSlot.objects.filter(date__in=[today, tomorrow])
    
    # Build response with only non-full slots
    available_slots_list = []
    for slot in slots:
        tokens_left = slot.max_tokens - slot.tokens_booked
        if tokens_left > 0:  # Only show slots with capacity
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
    """
    Book a new token with capacity enforcement
    URL: POST /api/core/book/
    Body: {
        "slot_id": 1,
        "patient_name": "Ramesh Sharma",
        "patient_age": 35,
        "patient_phone": "9841234567"
    }
    """
    # Get data from request
    slot_id = request.data.get('slot_id')
    patient_name = request.data.get('patient_name')
    patient_age = request.data.get('patient_age')
    patient_phone = request.data.get('patient_phone')
    
    # Validate all fields are present
    if not all([slot_id, patient_name, patient_age, patient_phone]):
        return Response({
            'success': False,
            'error': 'Missing required fields: slot_id, patient_name, patient_age, patient_phone'
        }, status=400)
    
    # Validate age is number
    try:
        patient_age = int(patient_age)
        if patient_age < 0 or patient_age > 120:
            raise ValueError()
    except ValueError:
        return Response({
            'success': False,
            'error': 'Patient age must be a valid number between 0 and 120'
        }, status=400)
    
    # Get the slot
    try:
        slot = ConsultationSlot.objects.get(id=slot_id)
    except ConsultationSlot.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Slot not found'
        }, status=404)
    
    # ========== CAPACITY ENFORCEMENT (Key Feature) ==========
    if slot.is_full:
        return Response({
            'success': False,
            'error': f'Slot is full! Maximum capacity is {slot.max_tokens} tokens per slot. Please choose another slot.'
        }, status=400)
    
    # Create the token
    token = Token.objects.create(
        slot=slot,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_phone=patient_phone
    )
    
    return Response({
        'success': True,
        'message': f'Token booked successfully!',
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


# ========== MEMBER B: CHECK-IN API ==========

@api_view(['GET'])
def search_patient(request):
    """
    Search for patient by token number or phone number
    URL: GET /api/core/search/?q=M10
    """
    search_term = request.query_params.get('q', '')
    
    if not search_term:
        return Response({
            'success': False,
            'error': 'Please provide a search term using ?q=token_or_phone'
        }, status=400)
    
    # Search by token number OR phone number
    tokens = Token.objects.filter(
        models.Q(token_number__icontains=search_term) |
        models.Q(patient_phone__icontains=search_term)
    ).select_related('slot__doctor__user')
    
    if not tokens.exists():
        return Response({
            'success': True,
            'message': 'No patients found',
            'patients': []
        })
    
    results = []
    for token in tokens:
        results.append({
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'patient_phone': token.patient_phone,
            'status': token.status,
            'estimated_time': token.estimated_time.strftime("%I:%M %p"),
            'doctor_name': str(token.slot.doctor),
            'is_elderly': token.is_elderly
        })
    
    return Response({
        'success': True,
        'count': len(results),
        'patients': results
    })


@api_view(['POST'])
def check_in_patient(request, token_id):
    """
    Reception checks in a patient
    URL: POST /api/core/check-in/1/
    """
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({
            'success': False,
            'error': f'Token with id {token_id} not found'
        }, status=404)
    
    # Verify patient is in booked status
    if token.status != 'booked':
        return Response({
            'success': False,
            'error': f'Cannot check in. Patient status is "{token.status}". Only "booked" patients can check in.'
        }, status=400)
    
    # Perform check-in
    token.check_in()
    
    return Response({
        'success': True,
        'message': f'Patient {token.patient_name} checked in successfully',
        'token': {
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'status': token.status,
            'checked_in_at': token.checked_in_at.strftime("%I:%M %p"),
            'waiting_position': 'Will be called shortly'
        }
    })


@api_view(['GET'])
def waiting_queue(request, doctor_id=None):
    """
    Get current waiting queue for a doctor or all doctors
    URL: GET /api/core/waiting-queue/ (all doctors)
         GET /api/core/waiting-queue/1/ (specific doctor)
    """
    today = timezone.now().date()
    
    # Get today's slots
    if doctor_id:
        slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    else:
        slots = ConsultationSlot.objects.filter(date=today)
    
    if not slots.exists():
        return Response({
            'success': True,
            'message': 'No active slots today',
            'queue': []
        })
    
    # Get all checked-in patients
    tokens = Token.objects.filter(
        slot__in=slots,
        status='checked_in'
    ).select_related('slot__doctor__user')
    
    # Build queue with priority (elderly first)
    queue_list = []
    for token in tokens:
        queue_list.append({
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'is_elderly': token.is_elderly,
            'doctor_name': str(token.slot.doctor),
            'checked_in_at': token.checked_in_at.strftime("%I:%M %p") if token.checked_in_at else None,
            'estimated_time': token.estimated_time.strftime("%I:%M %p")
        })
    
    # Sort: elderly first (True comes before False), then by token number
    queue_list.sort(key=lambda x: (not x['is_elderly'], x['token_number']))
    
    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'total_waiting': len(queue_list),
        'queue': queue_list
    })