from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.services.slot_config import ensure_slot_type_configs, get_all_slot_configs_serialized
from core.services.lab_catalog import serialize_lab_catalog


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return JsonResponse({'status': 'ok', 'message': 'General OPD API is running'})


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token(request):
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def public_slot_config(request):
    ensure_slot_type_configs()
    return Response({
        'success': True,
        'slots': get_all_slot_configs_serialized(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def public_lab_catalog(request):
    return Response({
        'success': True,
        'tests': serialize_lab_catalog(),
    })
