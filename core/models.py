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
    max_queue_size = models.IntegerField(default=5)
    is_throttled = models.BooleanField(default=False)
    
    def check_throttle(self):
        from django.utils import timezone
        today = timezone.now().date()
        queue_count = Token.objects.filter(
            slot__doctor=self,
            slot__date=today,
            status='checked_in'
        ).count()
        self.is_throttled = queue_count >= self.max_queue_size
        self.save(update_fields=['is_throttled'])
        return self.is_throttled
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
    
    # ADD THIS - the missing end_time property
    @property
    def end_time(self):
        times = {'morning': '11:00', 'afternoon': '14:00', 'evening': '17:00'}
        return times[self.slot_type]
    
    @property
    def tokens_booked(self):
        return self.tokens.filter(status__in=['booked', 'checked_in', 'consulting']).count()
    
    @property
    def is_full(self):
        return self.tokens_booked >= self.max_tokens
    
    def __str__(self):
        return f"{self.doctor} - {self.date} {self.slot_type} ({self.tokens_booked}/{self.max_tokens})"
    
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
        ('cancelled', 'Cancelled'),
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
    fee_exempted = models.BooleanField(default=False)
    original_token = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    consultation_started_at = models.DateTimeField(null=True, blank=True)
    consultation_ended_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.token_number:
            prefix_map = {'morning': 'M', 'afternoon': 'A', 'evening': 'E'}
            prefix = prefix_map.get(self.slot.slot_type, 'M')
            token_count = Token.objects.filter(slot=self.slot).count() + 1
            self.token_number = f"{prefix}{token_count}"
            
            slot_start = datetime.combine(self.slot.date, datetime.strptime(self.slot.start_time, '%H:%M').time())
            self.estimated_time = slot_start + timedelta(minutes=(token_count - 1) * self.slot.doctor.avg_consultation_time)
        
        if self.patient_age >= 60:
            self.is_elderly = True
            
        super().save(*args, **kwargs)
    
    # ========== ADD THESE METHODS ==========
    
    def check_in(self):
        """Mark token as checked in"""
        if self.status != 'booked':
            raise ValidationError(f"Cannot check in. Current status: {self.status}")
        self.status = 'checked_in'
        self.checked_in_at = timezone.now()
        self.save()
    
    def start_consultation(self):
        """Mark consultation as started"""
        if self.status != 'checked_in':
            raise ValidationError(f"Cannot start consultation. Current status: {self.status}")
        self.status = 'consulting'
        self.consultation_started_at = timezone.now()
        self.save()
    
    def complete_consultation(self):
        """Mark consultation as completed"""
        if self.status != 'consulting':
            raise ValidationError(f"Cannot complete consultation. Current status: {self.status}")
        self.status = 'completed'
        self.consultation_ended_at = timezone.now()
        self.save()
    
    def cancel(self):
        """Cancel the token"""
        if self.status != 'booked':
            raise ValidationError(f"Cannot cancel. Current status: {self.status}")
        self.status = 'cancelled'
        self.save()
    
    def waiting_time_minutes(self):
        """Calculate waiting time from check-in to consultation start"""
        if self.checked_in_at and self.consultation_started_at:
            return (self.consultation_started_at - self.checked_in_at).total_seconds() / 60
        return None
    
    def consultation_duration_minutes(self):
        """Calculate consultation duration"""
        if self.consultation_started_at and self.consultation_ended_at:
            return (self.consultation_ended_at - self.consultation_started_at).total_seconds() / 60
        return None
    
    def __str__(self):
        return f"Token {self.token_number} - {self.patient_name} ({self.status})"
    
    class Meta:
        ordering = ['estimated_time']