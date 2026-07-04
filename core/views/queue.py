from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import ConsultationSlot, Token
from core.permissions import IsReceptionistOrAdmin, IsStaff
from core.utils import serialize_token


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def waiting_queue(request, doctor_id=None):
    today = timezone.localdate()
    if doctor_id:
        slots = ConsultationSlot.objects.filter(doctor_id=doctor_id, date=today)
    else:
        slots = ConsultationSlot.objects.filter(date=today)

    tokens = Token.objects.filter(
        slot__in=slots,
        status='checked_in',
    ).select_related('slot__doctor__user', 'queue_entry')

    queue_list = [serialize_token(t, include_queue=True) for t in tokens]
    queue_list.sort(key=lambda x: (not x['is_elderly'], x['token_number']))

    return Response({
        'success': True,
        'queue_length': len(queue_list),
        'queue': queue_list,
    })
