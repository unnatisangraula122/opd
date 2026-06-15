from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsultationSlot, Token, DoctorProfile
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password
from accounts.models import User

# ========== HEALTH CHECK ==========
def health_check(request):
    return JsonResponse({'status': 'ok', 'message': 'Smart OPD API is running'})


# ========== BOOKING API ==========
@api_view(['GET'])
def available_slots(request):
    """Get all available slots for today and tomorrow"""
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    slots = ConsultationSlot.objects.filter(date__in=[today, tomorrow])
    
    available_slots_list = []
    for slot in slots:
        tokens_left = slot.max_tokens - slot.tokens_booked
        if tokens_left > 0:
            start_time = slot.start_time if hasattr(slot, 'start_time') else '09:00'
            end_time = slot.end_time if hasattr(slot, 'end_time') else '11:00'
            
            available_slots_list.append({
                'slot_id': slot.id,
                'doctor_name': str(slot.doctor),
                'doctor_id': slot.doctor.id,
                'date': slot.date,
                'slot_type': slot.slot_type,
                'start_time': start_time,
                'end_time': end_time,
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
    """Book a new token with capacity enforcement"""
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
    except ValueError:
        return Response({
            'success': False,
            'error': 'Invalid age'
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
            'error': f'Slot is full! Maximum {slot.max_tokens} tokens allowed.'
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


# ========== CHECK-IN API ==========
@api_view(['GET'])
def search_patient(request):
    """Search for patient by token number or phone number"""
    search_term = request.query_params.get('q', '')
    
    if not search_term:
        return Response({
            'success': False,
            'error': 'Search term required'
        }, status=400)
    
    tokens = Token.objects.filter(
        models.Q(token_number__icontains=search_term) |
        models.Q(patient_phone__icontains=search_term)
    ).select_related('slot__doctor__user')
    
    results = []
    for token in tokens:
        results.append({
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'patient_phone': token.patient_phone,
            'status': token.status,
            'estimated_time': token.estimated_time.strftime("%I:%M %p") if token.estimated_time else None,
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
    """Reception checks in a patient"""
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    if token.status != 'booked':
        return Response({
            'success': False,
            'error': f'Cannot check in. Current status: {token.status}'
        }, status=400)
    
    token.check_in()
    
    return Response({
        'success': True,
        'message': f'Patient {token.patient_name} checked in successfully',
        'token': {
            'token_id': token.id,
            'token_number': token.token_number,
            'status': token.status,
            'checked_in_at': token.checked_in_at.strftime("%I:%M %p") if token.checked_in_at else None
        }
    })


@api_view(['GET'])
def waiting_queue(request, doctor_id=None):
    """Get current waiting queue"""
    today = timezone.now().date()
    
    if doctor_id:
        slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    else:
        slots = ConsultationSlot.objects.filter(date=today)
    
    tokens = Token.objects.filter(
        slot__in=slots,
        status='checked_in'
    ).select_related('slot__doctor__user')
    
    queue_list = []
    for token in tokens:
        queue_list.append({
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'is_elderly': token.is_elderly,
            'doctor_name': str(token.slot.doctor),
            'checked_in_at': token.checked_in_at.strftime("%I:%M %p") if token.checked_in_at else None
        })
    
    queue_list.sort(key=lambda x: (not x['is_elderly'], x['token_number']))
    
    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'queue': queue_list
    })


# ========== DOCTOR CONSULTATION API ==========
@api_view(['GET'])
def doctor_queue(request, doctor_id):
    """Get prioritized queue for a doctor"""
    today = timezone.now().date()
    
    doctor_slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    
    if not doctor_slots.exists():
        return Response({
            'success': True,
            'doctor_id': doctor_id,
            'queue': []
        })
    
    tokens = Token.objects.filter(
        slot__in=doctor_slots,
        status='checked_in'
    ).select_related('slot')
    
    queue_list = []
    for token in tokens:
        queue_list.append({
            'position': len(queue_list) + 1,
            'token_id': token.id,
            'token_number': token.token_number,
            'patient_name': token.patient_name,
            'patient_age': token.patient_age,
            'is_elderly': token.is_elderly,
            'priority': 'HIGH' if token.is_elderly else 'NORMAL'
        })
    
    queue_list.sort(key=lambda x: (not x['is_elderly'], x['token_number']))
    
    for idx, patient in enumerate(queue_list):
        patient['position'] = idx + 1
    
    return Response({
        'success': True,
        'doctor_id': doctor_id,
        'queue_length': len(queue_list),
        'next_patient': queue_list[0] if queue_list else None,
        'queue': queue_list
    })


@api_view(['POST'])
def start_consultation(request, token_id):
    """Doctor starts consultation"""
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    if token.status != 'checked_in':
        return Response({
            'success': False,
            'error': f'Cannot start. Status: {token.status}'
        }, status=400)
    
    token.start_consultation()
    
    return Response({
        'success': True,
        'message': f'Consultation started for {token.patient_name}',
        'token': {
            'token_id': token.id,
            'token_number': token.token_number,
            'status': token.status
        }
    })


@api_view(['POST'])
def complete_consultation(request, token_id):
    """Doctor completes consultation"""
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    if token.status != 'consulting':
        return Response({
            'success': False,
            'error': f'Cannot complete. Status: {token.status}'
        }, status=400)
    
    token.complete_consultation()
    
    duration = None
    if token.consultation_started_at and token.consultation_ended_at:
        duration = round((token.consultation_ended_at - token.consultation_started_at).total_seconds() / 60, 1)
    
    return Response({
        'success': True,
        'message': f'Consultation completed for {token.patient_name}',
        'token': {
            'token_id': token.id,
            'token_number': token.token_number,
            'status': token.status,
            'consultation_duration_minutes': duration
        }
    })


@api_view(['GET'])
def next_patient(request, doctor_id):
    """Get next patient in queue"""
    today = timezone.now().date()
    
    doctor_slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    
    tokens = Token.objects.filter(
        slot__in=doctor_slots,
        status='checked_in'
    )
    
    sorted_tokens = sorted(tokens, key=lambda t: (not t.is_elderly, t.token_number))
    
    if not sorted_tokens:
        return Response({
            'success': True,
            'has_next': False
        })
    
    next_token = sorted_tokens[0]
    
    return Response({
        'success': True,
        'has_next': True,
        'next_patient': {
            'token_id': next_token.id,
            'token_number': next_token.token_number,
            'patient_name': next_token.patient_name,
            'patient_age': next_token.patient_age,
            'is_elderly': next_token.is_elderly
        }
    })


# ========== PATIENT AUTHENTICATION ==========
@api_view(['POST'])
def patient_register(request):
    """Register a new patient"""
    full_name = request.data.get('full_name')
    phone = request.data.get('phone')
    password = request.data.get('password')
    age = request.data.get('age')
    
    if not all([full_name, phone, password]):
        return Response({
            'success': False,
            'error': 'Full name, phone, and password required'
        }, status=400)
    
    if User.objects.filter(phone=phone).exists():
        return Response({
            'success': False,
            'error': 'Phone number already registered'
        }, status=400)
    
    username = f"pat_{phone}"
    
    user = User.objects.create(
        username=username,
        phone=phone,
        password=make_password(password),
        role='patient',
        first_name=full_name.split()[0] if ' ' in full_name else full_name
    )
    
    return Response({
        'success': True,
        'message': 'Registration successful! Please login.',
        'patient': {
            'patient_id': user.patient_id,
            'name': full_name,
            'phone': phone
        }
    })


@api_view(['POST'])
def patient_login(request):
    """Login a patient"""
    phone = request.data.get('phone')
    password = request.data.get('password')
    
    if not phone or not password:
        return Response({
            'success': False,
            'error': 'Phone and password required'
        }, status=400)
    
    try:
        user = User.objects.get(phone=phone, role='patient')
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Invalid credentials'
        }, status=401)
    
    if not user.check_password(password):
        return Response({
            'success': False,
            'error': 'Invalid credentials'
        }, status=401)
    
    login(request, user)
    
    return Response({
        'success': True,
        'message': f'Welcome back!',
        'patient': {
            'id': user.id,
            'patient_id': user.patient_id,
            'name': user.get_full_name() or user.username,
            'phone': user.phone
        }
    })


@api_view(['POST'])
def patient_logout(request):
    """Logout patient"""
    logout(request)
    return Response({'success': True, 'message': 'Logged out'})


@api_view(['GET'])
def get_current_patient(request):
    """Get current logged in patient"""
    if not request.user.is_authenticated or request.user.role != 'patient':
        return Response({'success': False, 'error': 'Not logged in'}, status=401)
    
    return Response({
        'success': True,
        'patient': {
            'id': request.user.id,
            'patient_id': request.user.patient_id,
            'name': request.user.get_full_name() or request.user.username,
            'phone': request.user.phone
        }
    })


@api_view(['GET'])
def get_patient_tokens(request):
    """Get all tokens for logged in patient"""
    if not request.user.is_authenticated or request.user.role != 'patient':
        return Response({'success': False, 'error': 'Please login'}, status=401)
    
    tokens = Token.objects.filter(
        patient_phone=request.user.phone
    ).select_related('slot__doctor__user').order_by('-created_at')
    
    tokens_data = []
    for token in tokens:
        tokens_data.append({
            'token_id': token.id,
            'token_number': token.token_number,
            'doctor_name': str(token.slot.doctor),
            'date': token.slot.date,
            'slot_type': token.slot.slot_type,
            'estimated_time': token.estimated_time.strftime("%I:%M %p") if token.estimated_time else None,
            'status': token.status,
            'is_elderly': token.is_elderly
        })
    
    return Response({
        'success': True,
        'tokens': tokens_data
    })


# ========== FOLLOW-UP ==========
@api_view(['POST'])
def create_followup(request, token_id):
    """Create a follow-up token"""
    try:
        original = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    is_free = timezone.now() <= original.created_at + timedelta(days=3)
    
    slot = ConsultationSlot.objects.filter(
        doctor=original.slot.doctor,
        date=timezone.now().date()
    ).first()
    
    if not slot:
        return Response({'success': False, 'error': 'No available slot'}, status=400)
    
    followup = Token.objects.create(
        slot=slot,
        patient_name=original.patient_name,
        patient_age=original.patient_age,
        patient_phone=original.patient_phone,
        is_followup=True,
        fee_exempted=is_free
    )
    
    return Response({
        'success': True,
        'followup_token': followup.token_number,
        'fee_exempted': is_free
    })


# ========== CANCEL TOKEN ==========
@api_view(['POST'])
def cancel_token(request, token_id):
    """Cancel a booked token"""
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    if token.status != 'booked':
        return Response({
            'success': False,
            'error': f'Cannot cancel. Status: {token.status}'
        }, status=400)
    
    token.status = 'cancelled'
    token.save()
    
    return Response({
        'success': True,
        'message': f'Token {token.token_number} cancelled'
    })


# ========== ANALYTICS ==========
@api_view(['GET'])
def analytics(request):
    """Get analytics for admin dashboard"""
    today = timezone.now().date()
    
    today_tokens = Token.objects.filter(slot__date=today)
    
    completed = today_tokens.filter(status='completed', checked_in_at__isnull=False)
    wait_times = []
    for t in completed:
        if t.consultation_started_at:
            wait = (t.consultation_started_at - t.checked_in_at).total_seconds() / 60
            wait_times.append(wait)
    
    avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
    
    doctor_queues = []
    for doctor in DoctorProfile.objects.all():
        queue = Token.objects.filter(
            slot__doctor=doctor,
            slot__date=today,
            status='checked_in'
        ).count()
        doctor_queues.append({
            'doctor': str(doctor),
            'queue': queue
        })
    
    return Response({
        'success': True,
        'date': today,
        'total_patients': today_tokens.count(),
        'completed': today_tokens.filter(status='completed').count(),
        'avg_waiting_minutes': round(avg_wait, 1),
        'doctor_queues': doctor_queues
    })