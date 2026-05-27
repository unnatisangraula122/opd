from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsultationSlot, Token
from django.utils import timezone
from datetime import timedelta

def health_check(request):
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