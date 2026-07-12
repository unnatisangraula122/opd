from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import ConsultationSlot, FollowupRule, LabOrder, Payment, Prescription, Token
from core.permissions import IsPatient
from core.utils import format_local_time, doctor_name_short, doctor_specialty, serialize_token


def _patient_token_filter(user, prefix=''):
    """Match tokens by linked account or phone number."""
    q = Q(**{f'{prefix}patient_phone': user.phone})
    if user.id:
        q |= Q(**{f'{prefix}patient_id': user.id})
    return q


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def get_patient_tokens(request):
    from core.services.workflow import expire_all_ended_slots

    expire_all_ended_slots()

    tokens = Token.objects.filter(
        _patient_token_filter(request.user)
    ).select_related('slot__doctor__user').order_by('-created_at')

    tokens_data = [serialize_token(t, include_queue=True) for t in tokens]
    return Response({'success': True, 'tokens': tokens_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_queue_status(request):
    from core.services.workflow import expire_all_ended_slots
    from core import constants as C

    expire_all_ended_slots()

    today = timezone.localdate()
    token = Token.objects.filter(
        _patient_token_filter(request.user),
        slot__date=today,
        status__in=['booked', 'checked_in', 'consulting', 'pending_lab', 'pending_pharmacy'],
    ).select_related('slot__doctor__user', 'patient').order_by('-created_at').first()

    if not token:
        return Response({'success': True, 'has_active': False})

    queue_position = None
    queue_length = 0
    try:
        entry = token.queue_entry
        if entry and entry.queue_status == 'waiting':
            queue_position = entry.queue_position
            from core.models import QueueEntry
            queue_length = QueueEntry.objects.filter(
                slot=token.slot,
                queue_status='waiting',
            ).count()
    except Exception:
        pass

    pharmacy = None
    pharmacy_status = None
    pharmacy_display = None
    try:
        pharmacy = token.pharmacy_queue_entry
        pharmacy_status = pharmacy.status
        pharmacy_display = C.PHARMACY_DISPLAY.get(pharmacy.status, pharmacy.status)
    except Exception:
        pass

    token_data = serialize_token(token, include_queue=True, include_workflow=True)
    if pharmacy_display:
        token_data['pharmacy_display'] = pharmacy_display

    return Response({
        'success': True,
        'has_active': True,
        'token': token_data,
        'queue_position': queue_position,
        'queue_length': queue_length,
        'pharmacy_status': pharmacy_status,
        'pharmacy_display': pharmacy_display,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_prescriptions(request):
    prescriptions = Prescription.objects.filter(
        _patient_token_filter(request.user, 'token__')
    ).select_related('token', 'consultation', 'token__slot__doctor').order_by('-id')

    data = []
    for p in prescriptions:
        consult = getattr(p, 'consultation', None)
        data.append({
            'token_number': p.token.token_number,
            'medicine_name': p.medicine_name,
            'dosage': p.dosage,
            'frequency': p.frequency,
            'duration_days': p.duration_days,
            'instructions': p.instructions,
            'dispensed': p.dispensed,
            'date': p.token.slot.date.isoformat(),
            'doctor_name': str(p.token.slot.doctor),
            'diagnosis': consult.diagnosis if consult else '',
            'symptoms': consult.symptoms if consult else '',
        })
    return Response({'success': True, 'prescriptions': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_lab_reports(request):
    orders = LabOrder.objects.filter(
        _patient_token_filter(request.user, 'token__'),
        status='completed',
    ).select_related('report', 'token', 'token__slot__doctor').order_by('-ordered_at')
    data = []
    for order in orders:
        report = getattr(order, 'report', None)
        data.append({
            'order_id': order.id,
            'token_number': order.token.token_number,
            'test_name': order.test_name,
            'findings': report.findings if report else '',
            'uploaded_at': report.uploaded_at.isoformat() if report else None,
            'report_url': report.report_file.url if report and report.report_file else None,
            'date': order.token.slot.date.isoformat(),
            'doctor_name': str(order.token.slot.doctor),
        })
    return Response({'success': True, 'lab_reports': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_bills(request):
    payments = Payment.objects.filter(
        _patient_token_filter(request.user, 'token__')
    ).select_related('token', 'token__slot__doctor').order_by('-paid_at')
    data = []
    for pay in payments:
        data.append({
            'payment_id': pay.id,
            'token_number': pay.token.token_number,
            'payment_type': pay.payment_type,
            'amount': float(pay.amount),
            'status': pay.status,
            'reference_number': pay.reference_number or '',
            'paid_at': pay.paid_at.isoformat() if pay.paid_at else None,
            'paid_at_display': format_local_time(pay.paid_at, '%d %b %Y, %I:%M %p') if pay.paid_at else None,
            'doctor_name': doctor_name_short(pay.token.slot.doctor),
            'doctor_specialization': doctor_specialty(pay.token.slot.doctor),
            'visit_date': pay.token.slot.date.isoformat(),
        })
    return Response({'success': True, 'bills': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatient])
def create_followup(request, token_id):
    try:
        original = Token.objects.filter(_patient_token_filter(request.user)).get(id=token_id)
    except Token.DoesNotExist:
        return Response({'success': False, 'error': 'Token not found'}, status=404)

    rule = FollowupRule.get_active()
    days = rule.exempt_within_days if rule else 3
    is_free = timezone.localdate() <= original.slot.date + timedelta(days=days)

    slot = ConsultationSlot.objects.filter(
        doctor=original.slot.doctor,
        date=timezone.localdate(),
    ).first()
    if not slot:
        return Response({'success': False, 'error': 'No available slot today'}, status=400)

    followup = Token.objects.create(
        slot=slot,
        patient=original.patient,
        patient_name=original.patient_name,
        patient_age=original.patient_age,
        patient_phone=original.patient_phone,
        patient_address=original.patient_address,
        is_followup=True,
        fee_exempted=is_free,
        original_token=original,
    )
    return Response({
        'success': True,
        'followup_token': followup.token_number,
        'fee_exempted': is_free,
        'token': serialize_token(followup),
    })
