from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import User


def _serialize_patient(user):
    return {
        'patient_id': user.patient_id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() or user.first_name,
        'phone': user.phone,
        'age': user.age,
        'address': user.address or '',
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def validate_old_patient(request):
    """Validate Patient ID + phone and return patient details for auto-fill."""
    patient_id = request.data.get('patient_id', '').strip()
    phone = request.data.get('phone', '').strip()

    if not patient_id or not phone:
        return Response({'success': False, 'error': 'Patient ID and phone number required'}, status=400)

    user = User.resolve_patient_id(patient_id)
    if not user:
        return Response({'success': False, 'error': 'Patient ID not found'}, status=404)

    if user.phone != phone:
        return Response({'success': False, 'error': 'Phone number does not match patient record'}, status=400)

    return Response({'success': True, 'patient': _serialize_patient(user)})


@api_view(['GET'])
@permission_classes([AllowAny])
def lookup_patient(request):
    """Query param lookup for reception/booking."""
    patient_id = request.query_params.get('patient_id', '').strip()
    phone = request.query_params.get('phone', '').strip()

    if not patient_id:
        return Response({'success': False, 'error': 'Patient ID required'}, status=400)

    user = User.resolve_patient_id(patient_id)
    if not user:
        return Response({'success': False, 'error': 'Patient not found'}, status=404)

    if phone and user.phone != phone:
        return Response({'success': False, 'error': 'Phone number does not match'}, status=400)

    return Response({'success': True, 'patient': _serialize_patient(user)})
