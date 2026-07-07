"""Lightweight sync endpoint — runs slot expiry and returns server clock."""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.services.workflow import expire_all_ended_slots


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_sync(request):
    expired_count = expire_all_ended_slots()
    return Response({
        'success': True,
        'server_time': timezone.now().isoformat(),
        'expired_count': expired_count,
    })
