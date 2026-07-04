from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.permissions import STAFF_ROLES, IsPatient, IsStaff
from core.utils import get_doctor_for_user


def _user_payload(user):
    data = {
        'id': user.id,
        'username': user.username,
        'name': user.get_full_name() or user.first_name or user.username,
        'role': user.role,
        'phone': user.phone,
    }
    if user.role == 'patient':
        data['patient_id'] = user.patient_id
    if user.role == 'doctor':
        profile = get_doctor_for_user(user)
        if profile:
            data['doctor_id'] = profile.id
            data['specialization'] = profile.specialization
    return data


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_register(request):
    full_name = request.data.get('full_name') or request.data.get('name')
    phone = request.data.get('phone')
    password = request.data.get('password')
    age = request.data.get('age')
    address = request.data.get('address', '')

    if not all([full_name, phone, password]):
        return Response({'success': False, 'error': 'Full name, phone, and password required'}, status=400)

    if User.objects.filter(phone=phone, role='patient').exists():
        return Response({'success': False, 'error': 'Phone number already registered'}, status=400)

    username = f'pat_{phone}'
    if User.objects.filter(username=username).exists():
        username = f'pat_{phone}_{User.objects.count()}'

    user = User.objects.create(
        username=username,
        phone=phone,
        password=make_password(password),
        role='patient',
        first_name=full_name.split()[0] if ' ' in full_name else full_name,
        last_name=' '.join(full_name.split()[1:]) if ' ' in full_name else '',
        age=int(age) if age else None,
        address=address,
    )

    return Response({
        'success': True,
        'message': 'Registration successful! Please login.',
        'patient': {
            'id': user.id,
            'patient_id': user.patient_id,
            'name': full_name,
            'phone': phone,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_login(request):
    phone = request.data.get('phone')
    password = request.data.get('password')
    patient_id = request.data.get('patient_id')

    user = None
    if patient_id:
        user = User.resolve_patient_id(patient_id)
    elif phone:
        try:
            user = User.objects.get(phone=phone, role='patient')
        except User.DoesNotExist:
            user = None

    if not user or not password or not user.check_password(password):
        return Response({'success': False, 'error': 'Invalid credentials'}, status=401)

    login(request, user)
    return Response({
        'success': True,
        'message': 'Welcome back!',
        'patient': _user_payload(user),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPatient])
def patient_logout(request):
    logout(request)
    return Response({'success': True, 'message': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPatient])
def get_current_patient(request):
    return Response({'success': True, 'patient': _user_payload(request.user)})


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_reset_password(request):
    phone = request.data.get('phone')
    password = request.data.get('password')
    if not phone or not password:
        return Response({'success': False, 'error': 'Phone and new password required'}, status=400)
    try:
        user = User.objects.get(phone=phone, role='patient')
    except User.DoesNotExist:
        return Response({'success': False, 'error': 'Phone number not found'}, status=404)
    user.password = make_password(password)
    user.save(update_fields=['password'])
    return Response({'success': True, 'message': 'Password reset successful'})


@api_view(['POST'])
@permission_classes([AllowAny])
def staff_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    expected_role = request.data.get('role')

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'success': False, 'error': 'Invalid credentials'}, status=401)
    if user.role not in STAFF_ROLES:
        return Response({'success': False, 'error': 'Not a staff account'}, status=403)
    if expected_role and user.role != expected_role:
        return Response({'success': False, 'error': f'Account is not a {expected_role}'}, status=403)

    login(request, user)
    return Response({'success': True, 'user': _user_payload(user)})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStaff])
def staff_logout(request):
    logout(request)
    return Response({'success': True, 'message': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_me(request):
    return Response({'success': True, 'user': _user_payload(request.user)})
