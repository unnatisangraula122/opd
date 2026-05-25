from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import User
from datetime import datetime, timedelta

class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'doctor'})
    specialization = models.CharField(max_length=100)
    avg_consultation_time = models.IntegerField(default=10)
    is_available = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Dr. {self.user.get_full_name()} - {self.specialization}"

class ConsultationSlot(models.Model):
    SLOT_TYPE = (
        ('morning', 'Morning (9:00-11:00)'),
        ('afternoon', 'Afternoon (12:00-14:00)'),
        ('evening', 'Evening (15:00-17:00)'),
    )
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField()
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPE)
    max_tokens = models.IntegerField(editable=False)
    
    def save(self, *args, **kwargs):
        self.max_tokens = 120 // self.doctor.avg_consultation_time
        super().save(*args, **kwargs)
    
    @property
    def start_time(self):
        times = {'morning': '09:00', 'afternoon': '12:00', 'evening': '15:00'}
        return times[self.slot_type]
    
    @property
    def tokens_booked(self):
        return self.tokens.filter(status__in=['booked', 'checked_in', 'consulting']).count()
    
    @property
    def is_full(self):
        return self.tokens_booked >= self.max_tokens
    
    class Meta:
        unique_together = ['doctor', 'date', 'slot_type']

class Token(models.Model):
    STATUS_CHOICES = (
        ('booked', 'Booked'),
        ('checked_in', 'Checked In'),
        ('consulting', 'Consulting'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('expired', 'Expired'),
    )
    
    slot = models.ForeignKey(ConsultationSlot, on_delete=models.CASCADE, related_name='tokens')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'patient'}, null=True, blank=True)
    patient_name = models.CharField(max_length=100)
    patient_age = models.IntegerField()
    patient_phone = models.CharField(max_length=15)
    token_number = models.CharField(max_length=10)
    estimated_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='booked')
    is_elderly = models.BooleanField(default=False)
    is_followup = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    consultation_started_at = models.DateTimeField(null=True, blank=True)
    consultation_ended_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.token_number:
            prefix_map = {'morning': 'M', 'afternoon': 'A', 'evening': 'E'}
            prefix = prefix_map[self.slot.slot_type]
            token_count = Token.objects.filter(slot=self.slot).count() + 1
            self.token_number = f"{prefix}{token_count}"
            
            slot_start = datetime.combine(self.slot.date, datetime.strptime(self.slot.start_time, '%H:%M').time())
            self.estimated_time = slot_start + timedelta(minutes=(token_count - 1) * self.slot.doctor.avg_consultation_time)
        
        if self.patient_age >= 60:
            self.is_elderly = True
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Token {self.token_number} - {self.patient_name} ({self.status})"
    
    class Meta:
        ordering = ['estimated_time']