from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import ConsultationSlot, LabOrder, LabQueueEntry, LabReport, Token
from core.permissions import IsLabTech, IsReceptionistOrAdmin
from core.services.sms import sms_lab_report_ready
from core.services.workflow import after_lab_report_uploaded
from core.utils import serialize_token


def _serialize_lab_order(order):
    entry = getattr(order, 'queue_entry', None)
    return {
        'order_id': order.id,
        'token_id': order.token_id,
        'token_number': order.token.token_number,
        'patient_name': order.token.patient_name,
        'test_name': order.test_name,
        'status': order.status,
        'queue_status': entry.status if entry else None,
        'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
        'lab_fee_paid': entry.lab_fee_paid if entry else False,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsLabTech])
def lab_queue(request):
    today = timezone.localdate()
    orders = LabOrder.objects.filter(
        token__slot__date=today,
        status__in=['fee_paid', 'in_queue', 'in_progress', 'completed'],
    ).select_related('token', 'queue_entry').order_by('ordered_at')
    pending = []
    processing = []
    completed = []
    for order in orders:
        item = _serialize_lab_order(order)
        entry = getattr(order, 'queue_entry', None)
        if order.status == 'completed':
            completed.append(item)
        elif entry and entry.status == 'in_progress':
            processing.append(item)
        else:
            pending.append(item)
    return Response({
        'success': True,
        'pending': pending,
        'processing': processing,
        'completed': completed,
        'all': pending + processing + completed,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsLabTech])
def lab_start_test(request, order_id):
    try:
        order = LabOrder.objects.get(id=order_id)
        entry = order.queue_entry
    except (LabOrder.DoesNotExist, LabQueueEntry.DoesNotExist):
        return Response({'success': False, 'error': 'Lab order not in queue'}, status=404)
    entry.start(request.user)
    return Response({'success': True, 'message': 'Test started', 'order': _serialize_lab_order(order)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsLabTech])
def lab_complete_test(request, order_id):
    try:
        order = LabOrder.objects.get(id=order_id)
        entry = order.queue_entry
    except (LabOrder.DoesNotExist, LabQueueEntry.DoesNotExist):
        return Response({'success': False, 'error': 'Lab order not in queue'}, status=404)

    findings = request.data.get('findings', '')
    report_file = request.FILES.get('report_file')

    entry.complete()
    report, _ = LabReport.objects.update_or_create(
        lab_order=order,
        defaults={
            'uploaded_by': request.user,
            'findings': findings,
        },
    )
    if report_file:
        report.report_file = report_file
        report.save()

    after_lab_report_uploaded(order)

    sms_result = None
    phone = order.token.patient_phone
    if phone:
        sms_result = sms_lab_report_ready(
            order.token.patient_name,
            order.test_name,
            phone,
        )

    payload = {
        'success': True,
        'message': 'Report uploaded',
        'order': _serialize_lab_order(order),
    }
    if sms_result is not None:
        payload['sms_sent'] = sms_result.success
        if not sms_result.success:
            payload['sms_warning'] = sms_result.error
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lab_reports_for_token(request, token_id):
    orders = LabOrder.objects.filter(token_id=token_id).select_related('report')
    data = []
    for order in orders:
        report = getattr(order, 'report', None)
        data.append({
            'order_id': order.id,
            'test_name': order.test_name,
            'status': order.status,
            'findings': report.findings if report else '',
            'uploaded_at': report.uploaded_at.isoformat() if report else None,
            'report_url': report.report_file.url if report and report.report_file else None,
        })
    return Response({'success': True, 'reports': data})
