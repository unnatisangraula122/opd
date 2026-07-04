from decimal import Decimal

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Payment, PharmacyQueueEntry, Prescription, Token
from core.permissions import IsPharmacist


def _serialize_pharmacy_entry(entry):
    prescriptions = Prescription.objects.filter(token=entry.token)
    return {
        'entry_id': entry.id,
        'token_id': entry.token_id,
        'token_number': entry.token.token_number,
        'patient_name': entry.token.patient_name,
        'status': entry.status,
        'total_bill': float(entry.total_bill),
        'payment_collected': entry.payment_collected,
        'prescriptions': [{
            'medicine_name': p.medicine_name,
            'dosage': p.dosage,
            'frequency': p.frequency,
            'duration_days': p.duration_days,
            'instructions': p.instructions,
            'dispensed': p.dispensed,
        } for p in prescriptions],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPharmacist])
def pharmacy_queue(request):
    entries = PharmacyQueueEntry.objects.filter(
        status__in=['waiting', 'dispensing', 'done']
    ).select_related('token').order_by('entered_at')

    waiting = []
    processing = []
    dispensed = []
    for entry in entries:
        item = _serialize_pharmacy_entry(entry)
        if entry.status == 'done':
            dispensed.append(item)
        elif entry.status == 'dispensing':
            processing.append(item)
        else:
            waiting.append(item)

    return Response({
        'success': True,
        'waiting': waiting,
        'processing': processing,
        'dispensed': dispensed,
        'queue': waiting + processing,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPharmacist])
def pharmacy_start_dispense(request, entry_id):
    try:
        entry = PharmacyQueueEntry.objects.get(id=entry_id)
    except PharmacyQueueEntry.DoesNotExist:
        return Response({'success': False, 'error': 'Entry not found'}, status=404)
    entry.start_dispensing(request.user)
    return Response({'success': True, 'entry': _serialize_pharmacy_entry(entry)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPharmacist])
def pharmacy_complete_dispense(request, entry_id):
    try:
        entry = PharmacyQueueEntry.objects.get(id=entry_id)
    except PharmacyQueueEntry.DoesNotExist:
        return Response({'success': False, 'error': 'Entry not found'}, status=404)

    amount = request.data.get('amount', entry.total_bill)
    entry.total_bill = Decimal(str(amount))
    entry.payment_collected = True
    entry.save()

    Payment.objects.create(
        token=entry.token,
        payment_type='pharmacy_fee',
        amount=entry.total_bill,
        status='paid',
        collected_by=request.user,
        paid_at=timezone.now(),
        reference_number=request.data.get('reference_number', f'pharm-{entry.id}'),
    )
    entry.complete()
    return Response({'success': True, 'message': 'Prescription dispensed', 'entry': _serialize_pharmacy_entry(entry)})
