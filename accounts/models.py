from django.contrib.auth.models import AbstractUser
from django.db import models, transaction


class PatientSerial(models.Model):
    """Atomic counter for serial Patient IDs (PAT0001, PAT0002, ...)."""
    last_serial = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Patient serial counter'

    @classmethod
    def next_code(cls):
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(pk=1)
            seq.last_serial += 1
            seq.save(update_fields=['last_serial'])
            return f'PAT{seq.last_serial:04d}'


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
    patient_code = models.CharField(max_length=12, blank=True, unique=True, null=True)

    @property
    def patient_id(self):
        if self.role == 'patient':
            return self.patient_code or None
        return None

    def assign_patient_code(self):
        if self.role == 'patient' and not self.patient_code:
            self.patient_code = PatientSerial.next_code()

    def save(self, *args, **kwargs):
        if self.role == 'patient' and not self.patient_code:
            self.assign_patient_code()
        super().save(*args, **kwargs)

    @classmethod
    def resolve_patient_id(cls, patient_id_str):
        """Resolve patient by canonical patient_code (PAT0001)."""
        if not patient_id_str:
            return None
        raw = patient_id_str.strip().upper()
        try:
            return cls.objects.get(patient_code=raw, role='patient')
        except cls.DoesNotExist:
            pass
        # Legacy P0001 format (pre-migration)
        if raw.startswith('P') and not raw.startswith('PAT') and raw[1:].isdigit():
            legacy_pat = f'PAT{int(raw[1:]):04d}'
            try:
                return cls.objects.get(patient_code=legacy_pat, role='patient')
            except cls.DoesNotExist:
                pass
        return None

    def __str__(self):
        return f"{self.username} ({self.role})"