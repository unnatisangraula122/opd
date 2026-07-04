from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('receptionist', 'Receptionist'),
        ('doctor', 'Doctor'),
        ('lab_tech', 'Lab Technician'),
        ('pharmacist', 'Pharmacist'),
        ('patient', 'Patient'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    phone = models.CharField(max_length=15, blank=True)
    age = models.IntegerField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    @property
    def patient_id(self):
        if self.role == 'patient':
            return f'PAT{self.id:06d}'
        return None

    @classmethod
    def resolve_patient_id(cls, patient_id_str):
        """Parse PAT000042 -> User pk 42."""
        if not patient_id_str:
            return None
        raw = patient_id_str.strip().upper()
        if raw.startswith('PAT'):
            raw = raw[3:]
        try:
            return cls.objects.get(pk=int(raw), role='patient')
        except (ValueError, cls.DoesNotExist):
            return None

    def __str__(self):
        return f"{self.username} ({self.role})"