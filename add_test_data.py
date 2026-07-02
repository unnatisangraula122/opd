"""
Add test data for Smart OPD testing
Run: python add_test_data.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from core.models import DoctorProfile, ConsultationSlot, Token
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import date

print("=" * 50)
print("ADDING TEST DATA TO SMART OPD")
print("=" * 50)

# 1. Create Doctor User
print("\n1. Creating doctor user...")
doctor_user, created = User.objects.get_or_create(
    username='drsharma',
    defaults={
        'first_name': 'Rajesh',
        'last_name': 'Sharma',
        'role': 'doctor',
        'password': make_password('doctor123'),
        'is_staff': True,
        'is_superuser': False
    }
)
if created:
    print("   ✅ Doctor user created: drsharma")
else:
    print("   ℹ️ Doctor user already exists")

# 2. Create Doctor Profile
print("\n2. Creating doctor profile...")
profile, created = DoctorProfile.objects.get_or_create(
    user=doctor_user,
    defaults={
        'specialization': 'Cardiologist',
        'avg_consultation_time': 10,
        'max_queue_size': 5,
        'is_available': True
    }
)
if created:
    print("   ✅ Doctor profile created")
else:
    print("   ℹ️ Doctor profile already exists")

# 3. Create Consultation Slot for today
print("\n3. Creating consultation slot for today...")
today = timezone.now().date()
slot, created = ConsultationSlot.objects.get_or_create(
    doctor=profile,
    date=today,
    defaults={'slot_type': 'morning'}
)
if created:
    print(f"   ✅ Slot created: {today} - Morning (max: {slot.max_tokens})")
else:
    print(f"   ℹ️ Slot already exists for {today}")

# 4. Create a test patient (optional)
print("\n4. Creating test patient...")
patient, created = User.objects.get_or_create(
    phone='9841234567',
    defaults={
        'username': 'patient_test',
        'password': make_password('patient123'),
        'role': 'patient',
        'first_name': 'Ramesh',
        'last_name': 'Sharma'
    }
)
if created:
    print("   ✅ Test patient created: 9841234567")
else:
    print("   ℹ️ Test patient already exists")

# 5. Create a token (optional)
print("\n5. Creating a test token...")
token = Token.objects.create(
    slot=slot,
    patient_name='Ramesh Sharma',
    patient_age=35,
    patient_phone='9841234567'
)
print(f"   ✅ Token created: {token.token_number}")

print("\n" + "=" * 50)
print("✅ TEST DATA ADDED SUCCESSFULLY!")
print("=" * 50)
print(f"\n📋 Summary:")
print(f"   Doctor: drsharma / doctor123")
print(f"   Patient: 9841234567 / patient123")
print(f"   Token: {token.token_number}")
print(f"   Admin: http://127.0.0.1:8000/admin/")