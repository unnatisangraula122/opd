from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Token
from core.permissions import IsReceptionistOrAdmin, IsStaff
from core.utils import serialize_token


def _serialize_queue_entry(token):
    data = serialize_token(token, include_queue=True)
    entry = getattr(token, 'queue_entry', None)
    if entry:
        data['queue_position'] = entry.queue_position
    return data


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def waiting_queue(request, doctor_id=None):
    today = timezone.localdate()
    tokens = Token.objects.filter(
        slot__date=today,
        status='checked_in',
    ).select_related('slot__doctor__user', 'queue_entry', 'patient')

    if doctor_id:
        tokens = tokens.filter(slot__doctor_id=doctor_id)

    slot_filter = request.query_params.get('slot_type')
    if slot_filter:
        tokens = tokens.filter(slot__slot_type=slot_filter.lower())

    queue_list = [_serialize_queue_entry(t) for t in tokens]
    queue_list.sort(key=lambda x: x.get('queue_position') or 999)

    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'queue': queue_list,
    })
