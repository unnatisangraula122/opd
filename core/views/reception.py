from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core import constants as C
from core.models import DoctorProfile, LabOrder, Payment, Token
from core.permissions import IsReceptionist, IsReceptionistOrAdmin
from core.services.sms import sms_patient_registration
from core.utils import is_elderly_by_age, serialize_token


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def search_patient(request):
    search_term = request.query_params.get('q', '')
    if not search_term:
        return Response({'success': False, 'error': 'Search term required'}, status=400)

    tokens = Token.objects.filter(
        models.Q(token_number__icontains=search_term) |
        models.Q(patient_phone__icontains=search_term) |
        models.Q(patient_name__icontains=search_term)
    ).select_related('slot__doctor__user').order_by('-created_at')[:20]

    results = [serialize_token(t) for t in tokens]
    return Response({'success': True, 'count': len(results), 'patients': results})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def check_in_patient(request, token_id):
    try:
        token = Token.objects.select_related('slot__doctor').get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)

    if token.slot.doctor.is_throttled:
        return Response({
            'success': False,
            'error': 'Auto-throttle active. Queue at capacity — wait for queue to clear.',
            'throttled': True,
        }, status=400)

    is_disabled = request.data.get('is_disabled')
    token.is_elderly = is_elderly_by_age(token.patient_age)
    if is_disabled is not None:
        token.is_disabled = bool(is_disabled)
    token.save(update_fields=['is_elderly', 'is_disabled'])

    try:
        token.check_in(receptionist=request.user)
    except ValidationError as exc:
        return Response({'success': False, 'error': str(exc)}, status=400)

    return Response({
        'success': True,
        'message': f'Patient {token.patient_name} checked in successfully',
        'token': serialize_token(token, include_queue=True),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def register_walkin_patient(request):
    """Register a new patient at reception and optionally link to a token."""
    full_name = request.data.get('full_name') or request.data.get('name')
    phone = request.data.get('phone')
    age = request.data.get('age')
    address = request.data.get('address', '')
    token_id = request.data.get('token_id')

    if not all([full_name, phone, age]):
        return Response({'success': False, 'error': 'Name, phone, and age required'}, status=400)

    user, created = User.objects.get_or_create(
        phone=phone,
        role='patient',
        defaults={
            'username': f'pat_{phone}',
            'first_name': full_name.split()[0],
            'last_name': ' '.join(full_name.split()[1:]) if ' ' in full_name else '',
            'age': int(age),
            'address': address,
        },
    )
    sms_result = None
    if not created:
        user.first_name = full_name.split()[0]
        user.last_name = ' '.join(full_name.split()[1:]) if ' ' in full_name else ''
        user.age = int(age)
        user.address = address
        if not user.patient_code:
            user.assign_patient_code()
        user.save()
    else:
        sms_result = sms_patient_registration(user.patient_id, phone)

    if token_id:
        try:
            token = Token.objects.get(id=token_id)
            token.patient = user
            token.patient_name = full_name
            token.patient_age = int(age)
            token.patient_phone = phone
            token.patient_address = address
            token.save()
        except Token.DoesNotExist:
            pass

    response_data = {
        'success': True,
        'patient': {
            'id': user.id,
            'patient_id': user.patient_id,
            'name': full_name,
            'phone': phone,
            'age': user.age,
        },
        'created': created,
    }
    if sms_result is not None:
        response_data['sms_sent'] = sms_result.success
        if not sms_result.success:
            response_data['sms_warning'] = sms_result.error
    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def reception_appointments(request):
    today = timezone.localdate()
    from datetime import timedelta
    tomorrow = today + timedelta(days=1)
    day_filter = request.query_params.get('day', 'all')
    view_filter = request.query_params.get('view', 'all')

    tokens = Token.objects.filter(
        slot__date__in=[today, tomorrow],
    ).select_related('slot__doctor__user', 'patient').order_by('slot__date', 'slot__slot_type', 'estimated_time')

    if day_filter == 'today':
        tokens = tokens.filter(slot__date=today)
    elif day_filter == 'tomorrow':
        tokens = tokens.filter(slot__date=tomorrow)

    if view_filter == 'active':
        tokens = tokens.filter(status__in=C.ACTIVE_STATUSES)
    elif view_filter == 'completed':
        tokens = tokens.filter(status=C.COMPLETED)
    elif view_filter == 'expired':
        tokens = tokens.filter(status__in=[C.EXPIRED, C.CANCELLED])

    serialized = [serialize_token(t, include_queue=True, include_workflow=True) for t in tokens]
    active = [a for a in serialized if a.get('is_active')]
    completed = [a for a in serialized if a['status'] == C.COMPLETED]
    expired = [a for a in serialized if a['status'] in (C.EXPIRED, C.CANCELLED)]

    return Response({
        'success': True,
        'appointments': serialized,
        'active': active,
        'completed': completed,
        'expired': expired,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def reception_lab_payments(request):
    orders = LabOrder.objects.filter(
        status__in=['ordered', 'fee_pending']
    ).select_related('token', 'consultation').order_by('ordered_at')
    data = []
    for order in orders:
        data.append({
            'order_id': order.id,
            'token_id': order.token_id,
            'token_number': order.token.token_number,
            'patient_name': order.token.patient_name,
            'test_name': order.test_name,
            'status': order.status,
            'amount': C.DEFAULT_LAB_FEE,
        })
    return Response({'success': True, 'lab_payments': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def pay_lab_fee(request, order_id):
    try:
        order = LabOrder.objects.get(id=order_id)
    except LabOrder.DoesNotExist:
        return Response({'success': False, 'error': 'Lab order not found'}, status=404)

    amount = request.data.get('amount', C.DEFAULT_LAB_FEE)
    Payment.objects.create(
        token=order.token,
        payment_type='lab_fee',
        amount=amount,
        status='paid',
        collected_by=request.user,
        paid_at=timezone.now(),
        reference_number=request.data.get('reference_number', f'lab-{order.id}'),
    )
    order.mark_fee_paid()
    return Response({'success': True, 'message': 'Lab fee paid', 'order_id': order.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsReceptionistOrAdmin])
def throttle_status(request):
    doctors = DoctorProfile.objects.select_related('user').all()
    data = []
    for doc in doctors:
        data.append({
            'doctor_id': doc.id,
            'doctor_name': str(doc),
            'is_throttled': doc.is_throttled,
            'max_queue_size': doc.max_queue_size,
        })
    return Response({'success': True, 'doctors': data})
