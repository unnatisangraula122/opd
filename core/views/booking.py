from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.models import ConsultationSlot, Payment, Token
from core.permissions import IsPatient, IsReceptionistOrAdmin
from core.services.sms import sms_token_booking
from core.utils import (
    CONSULTATION_BASE_FEE,
    duplicate_slot_booking_error,
    ensure_today_tomorrow_slots,
    get_daily_slots_for_dates,
    patient_has_active_slot_booking,
    OLD_PATIENT_BOOKING_MSG,
    serialize_slot,
    format_local_time,
    serialize_token,
    consultation_fee_with_charge,
)


@api_view(['GET'])
@permission_classes([AllowAny])
def available_slots(request):
    from core.services.slot_config import is_slot_bookable
    from core.services.workflow import expire_all_ended_slots

    expire_all_ended_slots()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    date_filter = request.query_params.get('date')

    dates = [today, tomorrow]
    if date_filter == 'today':
        dates = [today]
    elif date_filter == 'tomorrow':
        dates = [tomorrow]

    slots = get_daily_slots_for_dates(dates)

    available = []
    grouped = {'today': [], 'tomorrow': []}
    for slot in slots:
        if not is_slot_bookable(slot):
            continue
        serialized = serialize_slot(slot)
        available.append(serialized)
        key = 'today' if slot.date == today else 'tomorrow'
        grouped[key].append(serialized)

    return Response({
        'success': True,
        'today': today.isoformat(),
        'tomorrow': tomorrow.isoformat(),
        'count': len(available),
        'slots': available,
        'grouped': grouped,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def book_token(request):
    from core.services.workflow import expire_all_ended_slots

    expire_all_ended_slots()
    ensure_today_tomorrow_slots()
    slot_id = request.data.get('slot_id')
    patient_name = request.data.get('patient_name')
    patient_age = request.data.get('patient_age')
    patient_phone = request.data.get('patient_phone')
    patient_address = request.data.get('patient_address', '')
    is_disabled_raw = request.data.get('is_disabled')
    payment_method = request.data.get('payment_method', 'esewa')
    amount = request.data.get('amount')
    patient_id = request.data.get('patient_id')

    if not all([slot_id, patient_name, patient_age]) and not patient_id:
        return Response({'success': False, 'error': 'Missing required fields'}, status=400)

    if patient_id and not patient_phone:
        return Response({'success': False, 'error': 'Patient phone required for old patients'}, status=400)

    if not patient_id and patient_phone:
        existing_patient = User.objects.filter(phone=patient_phone, role='patient').first()
        if existing_patient and existing_patient.patient_code:
            return Response({
                'success': False,
                'error': OLD_PATIENT_BOOKING_MSG,
                'requires_old_patient': True,
            }, status=400)

    patient_user = None
    if patient_id:
        patient_user = User.resolve_patient_id(patient_id)
        if not patient_user:
            return Response({'success': False, 'error': 'Patient ID not found'}, status=404)
        if patient_user.phone != patient_phone:
            return Response({'success': False, 'error': 'Phone number does not match patient record'}, status=400)
        patient_name = patient_name or (patient_user.get_full_name() or patient_user.username)
        patient_age = patient_age or patient_user.age or 30
        patient_address = patient_address or patient_user.address or ''

    try:
        patient_age = int(patient_age)
    except (TypeError, ValueError):
        return Response({'success': False, 'error': 'Invalid age'}, status=400)

    try:
        slot = ConsultationSlot.objects.select_related('doctor').get(id=slot_id)
    except ConsultationSlot.DoesNotExist:
        return Response({'success': False, 'error': 'Slot not found'}, status=404)

    from core.services.slot_config import is_slot_bookable
    if not is_slot_bookable(slot):
        if slot.is_full:
            return Response({'success': False, 'error': f'Slot is full! Maximum {slot.max_tokens} tokens allowed.'}, status=400)
        return Response({'success': False, 'error': 'This slot has already passed. Please choose another slot or date.'}, status=400)

    if slot.doctor.is_throttled:
        return Response({'success': False, 'error': 'Doctor queue is at capacity. Check-in throttled.'}, status=400)

    if not patient_user:
        if request.user.is_authenticated and request.user.role == 'patient':
            patient_user = request.user
        elif patient_phone:
            patient_user = User.objects.filter(phone=patient_phone, role='patient').first()

    if patient_has_active_slot_booking(slot, patient_user=patient_user, patient_phone=patient_phone):
        return Response({
            'success': False,
            'error': duplicate_slot_booking_error(slot),
        }, status=400)

    if is_disabled_raw is not None:
        disabled_flag = bool(is_disabled_raw)
    elif patient_user:
        disabled_flag = bool(getattr(patient_user, 'is_disabled', False))
    else:
        disabled_flag = False

    token = Token.objects.create(
        slot=slot,
        patient=patient_user,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_phone=patient_phone,
        patient_address=patient_address,
        is_disabled=disabled_flag,
    )

    base, service, total = consultation_fee_with_charge()
    paid_amount = Decimal(str(amount)) if amount is not None else total
    Payment.objects.create(
        token=token,
        payment_type='consultation_fee',
        amount=paid_amount,
        status='paid',
        reference_number=f'{payment_method}-{token.id}',
        paid_at=timezone.now(),
    )

    estimated_str = format_local_time(token.estimated_time) or ''
    sms_result = sms_token_booking(
        token.token_number,
        estimated_str,
        patient_phone,
        token.slot.start_time,
    )

    response_payload = {
        'success': True,
        'message': 'Token booked successfully!',
        'token': serialize_token(token),
        'sms_sent': sms_result.success,
    }
    if not sms_result.success:
        response_payload['sms_warning'] = sms_result.error
    return Response(response_payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatient])
def cancel_token(request, token_id):
    try:
        token = Token.objects.get(id=token_id, patient_phone=request.user.phone)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    try:
        token.cancel()
    except Exception as exc:
        return Response({'success': False, 'error': str(exc)}, status=400)
    return Response({'success': True, 'message': f'Token {token.token_number} cancelled'})


@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_token_public(request, token_id):
    try:
        token = Token.objects.get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)
    if token.status != 'booked':
        return Response({'success': False, 'error': f'Cannot cancel. Status: {token.status}'}, status=400)
    token.cancel()
    return Response({'success': True, 'message': f'Token {token.token_number} cancelled'})
