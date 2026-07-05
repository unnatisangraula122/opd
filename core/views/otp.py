from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.services.otp import send_otp, verify_otp


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_send(request):
    phone = request.data.get('phone', '').strip()
    purpose = request.data.get('purpose', 'login')
    if purpose not in ('registration', 'login', 'password_reset'):
        return Response({'success': False, 'error': 'Invalid purpose'}, status=400)
    if not phone:
        return Response({'success': False, 'error': 'Phone number required'}, status=400)
    result = send_otp(phone, purpose)
    status = 200 if result.get('success') else 400
    return Response(result, status=status)


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_verify(request):
    phone = request.data.get('phone', '').strip()
    otp = request.data.get('otp', '').strip()
    purpose = request.data.get('purpose', 'login')
    if not phone or not otp:
        return Response({'success': False, 'error': 'Phone and OTP required'}, status=400)
    result = verify_otp(phone, otp, purpose)
    status = 200 if result.get('success') else 400
    return Response(result, status=status)
