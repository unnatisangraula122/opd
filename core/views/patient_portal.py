from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import ConsultationSlot, FollowupRule, LabOrder, Payment, Prescription, Token
from core.permissions import IsPatient
from core.utils import serialize_token


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def get_patient_tokens(request):
    tokens = Token.objects.filter(
        patient_phone=request.user.phone
    ).select_related('slot__doctor__user').order_by('-created_at')

    tokens_data = [serialize_token(t, include_queue=True) for t in tokens]
    return Response({'success': True, 'tokens': tokens_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_queue_status(request):
    today = timezone.localdate()
    token = Token.objects.filter(
        patient_phone=request.user.phone,
        slot__date=today,
        status__in=['booked', 'checked_in', 'consulting'],
    ).select_related('slot__doctor', 'queue_entry').order_by('-created_at').first()

    if not token:
        return Response({'success': True, 'has_active': False})

    queue_position = None
    queue_length = 0
    if hasattr(token, 'queue_entry'):
        queue_position = token.queue_entry.queue_position
        from core.models import QueueEntry
        queue_length = QueueEntry.objects.filter(
            slot=token.slot,
            queue_status='waiting',
        ).count()

    return Response({
        'success': True,
        'has_active': True,
        'token': serialize_token(token, include_queue=True),
        'queue_position': queue_position,
        'queue_length': queue_length,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_prescriptions(request):
    prescriptions = Prescription.objects.filter(
        token__patient_phone=request.user.phone
    ).select_related('token', 'consultation').order_by('-id')

    data = []
    for p in prescriptions:
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
        })
    return Response({'success': True, 'prescriptions': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_lab_reports(request):
    orders = LabOrder.objects.filter(
        token__patient_phone=request.user.phone,
        status='completed',
    ).select_related('report', 'token')
    data = []
    for order in orders:
        report = getattr(order, 'report', None)
        data.append({
            'token_number': order.token.token_number,
            'test_name': order.test_name,
            'findings': report.findings if report else '',
            'uploaded_at': report.uploaded_at.isoformat() if report else None,
            'date': order.token.slot.date.isoformat(),
        })
    return Response({'success': True, 'lab_reports': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_bills(request):
    payments = Payment.objects.filter(
        token__patient_phone=request.user.phone
    ).select_related('token').order_by('-paid_at')
    data = []
    for pay in payments:
        data.append({
            'token_number': pay.token.token_number,
            'payment_type': pay.payment_type,
            'amount': float(pay.amount),
            'status': pay.status,
            'paid_at': pay.paid_at.isoformat() if pay.paid_at else None,
        })
    return Response({'success': True, 'bills': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatient])
def create_followup(request, token_id):
    try:
        original = Token.objects.get(id=token_id, patient_phone=request.user.phone)
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
