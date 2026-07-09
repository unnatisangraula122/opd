from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.models import (
    ConsultationSlot, DailyAnalytics, DoctorProfile, FollowupRule,
    ThrottleLog, Token,
)
from core.permissions import IsAdmin
from core.services.analytics import compute_kpis, get_recommendations
from core.utils import ensure_today_tomorrow_slots, serialize_slot
from core.services.slot_config import (
    ensure_slot_type_configs,
    get_all_slot_configs_serialized,
    get_slot_type_config,
    parse_time_value,
    refresh_consultation_slot_capacities,
    SLOT_TYPES,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_doctors(request):
    doctors = DoctorProfile.objects.select_related('user').all()
    data = []
    for doc in doctors:
        data.append({
            'id': doc.id,
            'name': str(doc),
            'username': doc.user.username,
            'specialization': doc.specialization,
            'qualification': doc.qualification,
            'avg_consultation_time': doc.avg_consultation_time,
            'is_available': doc.is_available,
            'max_queue_size': doc.max_queue_size,
            'is_throttled': doc.is_throttled,
        })
    return Response({'success': True, 'doctors': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_add_doctor(request):
    full_name = request.data.get('full_name') or request.data.get('name')
    username = request.data.get('username')
    password = request.data.get('password', 'doctor123')
    specialization = request.data.get('specialization', 'General')
    qualification = request.data.get('qualification', '')
    avg_consultation_time = int(request.data.get('avg_consultation_time', 10))

    if not full_name or not username:
        return Response({'success': False, 'error': 'Name and username required'}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({'success': False, 'error': 'Username already exists'}, status=400)

    parts = full_name.replace('Dr.', '').strip().split()
    user = User.objects.create(
        username=username,
        password=make_password(password),
        role='doctor',
        first_name=parts[0] if parts else full_name,
        last_name=' '.join(parts[1:]) if len(parts) > 1 else '',
    )
    profile = DoctorProfile.objects.create(
        user=user,
        specialization=specialization,
        qualification=qualification,
        avg_consultation_time=avg_consultation_time,
    )
    ensure_today_tomorrow_slots()
    return Response({
        'success': True,
        'doctor': {'id': profile.id, 'name': str(profile), 'username': username},
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_update_doctor(request, doctor_id):
    try:
        profile = DoctorProfile.objects.get(id=doctor_id)
    except DoctorProfile.DoesNotExist:
        return Response({'success': False, 'error': 'Doctor not found'}, status=404)

    for field in ('specialization', 'qualification', 'avg_consultation_time', 'is_available', 'max_queue_size'):
        if field in request.data:
            setattr(profile, field, request.data[field])
    profile.save()
    ensure_today_tomorrow_slots()
    return Response({'success': True, 'doctor_id': profile.id})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_slot_config(request):
    ensure_slot_type_configs()
    if request.method == 'GET':
        slots = get_all_slot_configs_serialized()
        return Response({
            'success': True,
            'slots': slots,
        })

    slots_payload = request.data.get('slots')
    if not isinstance(slots_payload, dict):
        return Response({'success': False, 'error': 'slots object required'}, status=400)

    for slot_type in SLOT_TYPES:
        payload = slots_payload.get(slot_type)
        if not payload:
            continue
        config = get_slot_type_config(slot_type)
        if 'start_time' in payload:
            config.start_time = parse_time_value(payload['start_time'])
        if 'end_time' in payload:
            config.end_time = parse_time_value(payload['end_time'])
        if 'avg_consultation_minutes' in payload:
            config.avg_consultation_minutes = max(int(payload['avg_consultation_minutes']), 1)
        if 'checkin_opens_minutes_before' in payload:
            config.checkin_opens_minutes_before = max(int(payload['checkin_opens_minutes_before']), 0)
        if config.end_time <= config.start_time:
            return Response({
                'success': False,
                'error': f'{slot_type.title()} end time must be after start time',
            }, status=400)
        config.save()

    refresh_consultation_slot_capacities()
    ensure_today_tomorrow_slots()
    return Response({
        'success': True,
        'slots': get_all_slot_configs_serialized(),
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_throttle_config(request):
    if request.method == 'GET':
        doc = DoctorProfile.objects.first()
        return Response({
            'success': True,
            'max_queue_size': doc.max_queue_size if doc else 5,
            'is_throttled': any(d.is_throttled for d in DoctorProfile.objects.all()),
        })

    max_queue = int(request.data.get('max_queue_size', 5))
    DoctorProfile.objects.update(max_queue_size=max_queue)
    for doc in DoctorProfile.objects.all():
        doc.check_throttle()
    return Response({'success': True, 'max_queue_size': max_queue})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_throttle_logs(request):
    logs = ThrottleLog.objects.select_related('slot__doctor').order_by('-triggered_at')[:50]
    return Response({
        'success': True,
        'logs': [{
            'action': log.action,
            'doctor': str(log.slot.doctor),
            'queue_length': log.queue_length_at_trigger,
            'threshold': log.threshold_at_trigger,
            'triggered_at': log.triggered_at.strftime('%Y-%m-%d %H:%M'),
        } for log in logs],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def analytics(request):
    kpis = compute_kpis()
    recommendations = [
        {
            'id': r.id,
            'doctor': str(r.doctor),
            'configured_avg_minutes': r.configured_avg_minutes,
            'actual_avg_minutes': float(r.actual_avg_minutes),
            'variance_percent': float(r.variance_percent),
            'recommended_avg_minutes': r.recommended_avg_minutes,
            'message': r.message,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for r in get_recommendations()
    ]
    return Response({
        'success': True,
        **kpis,
        'recommendations': recommendations,
        'throttle_events': ThrottleLog.objects.filter(
            triggered_at__date=timezone.localdate(), action='throttled'
        ).count(),
    })
