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
from core.utils import format_local_time

# ========== HEALTH CHECK ==========
def health_check(request):
    return JsonResponse({'status': 'ok', 'message': 'General OPD API is running'})


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
            'estimated_time': format_local_time(token.estimated_time),
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
            'estimated_time': format_local_time(token.estimated_time),
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
            'checked_in_at': format_local_time(token.checked_in_at),
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
            'checked_in_at': format_local_time(token.checked_in_at),
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
            'estimated_time': format_local_time(token.estimated_time),
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

# ========== NEW: CONSULTATION NOTES ==========
@api_view(['POST'])
def save_consultation_notes(request, token_id):
    """Doctor saves consultation notes, diagnosis, and followup"""
    from .models import Consultation
    
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    if token.status not in ['consulting', 'completed']:
        return Response({
            'success': False,
            'error': 'Consultation not in progress'
        }, status=400)
    
    consultation, created = Consultation.objects.get_or_create(
        token=token,
        defaults={'doctor': token.slot.doctor}
    )
    
    consultation.symptoms = request.data.get('symptoms', consultation.symptoms)
    consultation.diagnosis = request.data.get('diagnosis', consultation.diagnosis)
    consultation.notes = request.data.get('notes', consultation.notes)
    consultation.requires_lab = request.data.get('requires_lab', consultation.requires_lab)
    consultation.requires_followup = request.data.get('requires_followup', consultation.requires_followup)
    
    if consultation.requires_followup:
        followup_date = request.data.get('followup_date')
        if followup_date:
            consultation.followup_date = followup_date
        consultation.followup_instructions = request.data.get('followup_instructions', '')
    
    consultation.save()
    
    return Response({
        'success': True,
        'message': 'Consultation notes saved',
        'consultation': {
            'id': consultation.id,
            'diagnosis': consultation.diagnosis,
            'requires_lab': consultation.requires_lab,
            'requires_followup': consultation.requires_followup
        }
    })


# ========== NEW: LAB ORDERS ==========
@api_view(['POST'])
def create_lab_order(request, token_id):
    """Doctor orders lab test"""
    from .models import Consultation, LabOrder
    
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    try:
        consultation = Consultation.objects.get(token=token)
    except Consultation.DoesNotExist:
        return Response({'success': False, 'error': 'Consultation not found'}, status=404)
    
    test_name = request.data.get('test_name')
    instructions = request.data.get('instructions', '')
    
    if not test_name:
        return Response({'success': False, 'error': 'Test name required'}, status=400)
    
    lab_order = LabOrder.objects.create(
        consultation=consultation,
        token=token,
        test_name=test_name,
        instructions=instructions
    )
    
    # Update token status
    token.status = 'pending_lab'
    token.save()
    
    return Response({
        'success': True,
        'message': 'Lab order created',
        'lab_order': {
            'id': lab_order.id,
            'test_name': lab_order.test_name,
            'status': lab_order.status
        }
    })


@api_view(['GET'])
def lab_queue(request):
    """Get lab queue for technician"""
    from .models import LabQueueEntry
    
    lab_entries = LabQueueEntry.objects.filter(
        status='waiting'
    ).select_related('lab_order', 'token')
    
    queue_list = []
    for entry in lab_entries:
        queue_list.append({
            'entry_id': entry.id,
            'test_name': entry.lab_order.test_name,
            'token_number': entry.token.token_number,
            'patient_name': entry.token.patient_name,
            'status': entry.status,
            'lab_fee_paid': entry.lab_fee_paid
        })
    
    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'queue': queue_list
    })


@api_view(['POST'])
def complete_lab_order(request, lab_order_id):
    """Lab technician completes lab order"""
    from .models import LabOrder
    
    try:
        lab_order = LabOrder.objects.get(id=lab_order_id)
    except LabOrder.DoesNotExist:
        return Response({'success': False, 'error': 'Lab order not found'}, status=404)
    
    if lab_order.status != 'in_queue':
        return Response({
            'success': False,
            'error': f'Cannot complete. Status: {lab_order.status}'
        }, status=400)
    
    lab_order.status = 'completed'
    lab_order.completed_at = timezone.now()
    lab_order.save()
    
    # Update queue entry
    if hasattr(lab_order, 'queue_entry'):
        entry = lab_order.queue_entry
        entry.status = 'done'
        entry.completed_at = timezone.now()
        entry.save()
    
    return Response({
        'success': True,
        'message': 'Lab order completed'
    })


# ========== NEW: PHARMACY QUEUE ==========
@api_view(['GET'])
def pharmacy_queue(request):
    """Get pharmacy queue for pharmacist"""
    from .models import PharmacyQueueEntry
    
    pharmacy_entries = PharmacyQueueEntry.objects.filter(
        status='waiting'
    ).select_related('token')
    
    queue_list = []
    for entry in pharmacy_entries:
        queue_list.append({
            'entry_id': entry.id,
            'token_number': entry.token.token_number,
            'patient_name': entry.token.patient_name,
            'status': entry.status,
            'total_bill': entry.total_bill
        })
    
    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'queue': queue_list
    })


# ========== NEW: PAYMENT ==========
@api_view(['POST'])
def create_payment(request, token_id):
    """Create a payment record"""
    from .models import Payment
    
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    
    payment_type = request.data.get('payment_type')
    amount = request.data.get('amount')
    
    if not payment_type or not amount:
        return Response({'success': False, 'error': 'Payment type and amount required'}, status=400)
    
    payment = Payment.objects.create(
        token=token,
        payment_type=payment_type,
        amount=amount
    )
    
    return Response({
        'success': True,
        'message': 'Payment record created',
        'payment': {
            'id': payment.id,
            'payment_type': payment.payment_type,
            'amount': payment.amount,
            'status': payment.status
        }
    })


# ========== NEW: PATIENT HISTORY ==========
@api_view(['GET'])
def patient_history(request, phone):
    """Get complete patient history with prescriptions and consultations"""
    from .models import Consultation, Prescription
    
    tokens = Token.objects.filter(patient_phone=phone).order_by('-created_at')
    
    if not tokens.exists():
        return Response({
            'success': True,
            'patient_phone': phone,
            'history': [],
            'message': 'No records found'
        })
    
    history = []
    for token in tokens:
        record = {
            'token_number': token.token_number,
            'date': token.created_at.strftime("%Y-%m-%d %H:%M"),
            'doctor': str(token.slot.doctor),
            'status': token.status,
            'is_elderly': token.is_elderly,
            'consultation': None,
            'prescriptions': []
        }
        
        # Get consultation notes
        if hasattr(token, 'consultation'):
            consult = token.consultation
            record['consultation'] = {
                'diagnosis': consult.diagnosis,
                'symptoms': consult.symptoms,
                'notes': consult.notes,
                'requires_followup': consult.requires_followup
            }
        
        # Get prescriptions
        prescriptions = Prescription.objects.filter(token=token)
        for presc in prescriptions:
            record['prescriptions'].append({
                'medicine': presc.medicine_name,
                'dosage': presc.dosage,
                'frequency': presc.frequency,
                'duration_days': presc.duration_days,
                'dispensed': presc.dispensed
            })
        
        history.append(record)
    
    return Response({
        'success': True,
        'patient_phone': phone,
        'total_visits': len(history),
        'history': history
    })