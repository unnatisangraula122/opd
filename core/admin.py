from django.contrib import admin
from .models import DoctorProfile, ConsultationSlot, Token

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'avg_consultation_time']

@admin.register(ConsultationSlot)
class ConsultationSlotAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'date', 'slot_type', 'max_tokens']

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ['token_number', 'patient_name', 'status']