from django.contrib import admin
from .models import (
    DoctorProfile,
    ConsultationSlot,
    Token,
    QueueEntry,
    ThrottleLog,
    Consultation,
    LabOrder,
    LabQueueEntry,
    LabReport,
    Prescription,
    PharmacyQueueEntry,
    Payment,
    FollowupRule,
    DailyAnalytics
)

# ============================================================
# 1. DOCTOR PROFILE
# ============================================================
@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'specialization',
        'qualification',
        'avg_consultation_time',
        'is_available',
        'is_throttled',
        'max_queue_size'
    ]
    list_filter = ['is_available', 'is_throttled', 'specialization']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'specialization']
    readonly_fields = ['is_throttled']
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'specialization', 'qualification')
        }),
        ('Consultation Settings', {
            'fields': ('avg_consultation_time', 'is_available')
        }),
        ('Queue Management', {
            'fields': ('max_queue_size', 'is_throttled'),
        }),
    )


# ============================================================

# 2. CONSULTATION SLOT
# ============================================================
@admin.register(ConsultationSlot)
class ConsultationSlotAdmin(admin.ModelAdmin):
    list_display = [
        'doctor',
        'date',
        'slot_type',
        'start_time',
        'end_time',
        'max_tokens',
        'tokens_booked',
        'is_full'
    ]
    list_filter = ['date', 'slot_type', 'doctor']
    search_fields = ['doctor__user__username', 'doctor__specialization']
    readonly_fields = ['max_tokens', 'tokens_booked', 'is_full']
    ordering = ['-date', 'slot_type']


# ============================================================
# 3. TOKEN (Patient Appointment)
# ============================================================
@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = [
        'token_number',
        'patient_name',
        'patient_phone',
        'status',
        'estimated_time',
        'is_elderly',
        'is_followup'
    ]
    list_filter = ['status', 'is_elderly', 'is_followup', 'slot__date']
    search_fields = [
        'token_number',
        'patient_name',
        'patient_phone',
        'patient__username'
    ]
    readonly_fields = [
        'token_number',
        'estimated_time',
        'created_at',
        'checked_in_at',
        'consultation_started_at',
        'consultation_ended_at',
        'is_elderly'
    ]
    fieldsets = (
        ('Token Information', {
            'fields': ('token_number', 'slot', 'status', 'estimated_time')
        }),
        ('Patient Information', {
            'fields': ('patient', 'patient_name', 'patient_age', 'patient_phone', 'patient_address')
        }),
        ('Special Flags', {
            'fields': ('is_elderly', 'is_disabled', 'is_followup', 'fee_exempted', 'original_token')
        }),
        ('Check-in Details', {
            'fields': ('receptionist', 'checkin_status', 'checked_in_at')
        }),
        ('Consultation Timestamps', {
            'fields': ('consultation_started_at', 'consultation_ended_at')
        }),
        ('System Fields', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# ============================================================
# 4. QUEUE ENTRY (Live Doctor Queue)
# ============================================================
@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'doctor',
        'queue_position',
        'priority',
        'queue_status',
        'entered_at'
    ]
    list_filter = ['priority', 'queue_status', 'doctor']
    search_fields = ['token__token_number', 'token__patient_name']
    readonly_fields = ['queue_position', 'wait_minutes']
    ordering = ['-entered_at']


# ============================================================
# 5. THROTTLE LOG (Audit Trail)
# ============================================================
@admin.register(ThrottleLog)
class ThrottleLogAdmin(admin.ModelAdmin):
    list_display = [
        'slot',
        'action',
        'queue_length_at_trigger',
        'threshold_at_trigger',
        'triggered_by',
        'triggered_at'
    ]
    list_filter = ['action', 'triggered_by', 'triggered_at']
    search_fields = ['slot__doctor__user__username']
    readonly_fields = ['triggered_at']
    ordering = ['-triggered_at']


# ============================================================
# 6. CONSULTATION (Doctor's Notes)
# ============================================================
@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'diagnosis',
        'requires_lab',
        'requires_followup',
        'followup_date',
        'created_at'
    ]
    list_filter = ['requires_lab', 'requires_followup']
    search_fields = ['diagnosis', 'notes', 'token__token_number', 'token__patient_name']
    fieldsets = (
        ('Consultation', {
            'fields': ('token', 'symptoms', 'diagnosis', 'notes')
        }),
        ('Follow-up', {
            'fields': ('requires_followup', 'followup_date', 'followup_instructions')
        }),
        ('Lab', {
            'fields': ('requires_lab',)
        }),
        ('System Fields', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


# ============================================================
# 7. LAB ORDER
# ============================================================
@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'test_name',
        'status',
        'ordered_at',
        'completed_at'
    ]
    list_filter = ['status']
    search_fields = ['test_name', 'token__token_number', 'token__patient_name']
    readonly_fields = ['ordered_at']


# ============================================================
# 8. LAB QUEUE ENTRY
# ============================================================
@admin.register(LabQueueEntry)
class LabQueueEntryAdmin(admin.ModelAdmin):
    list_display = [
        'lab_order',
        'token',
        'status',
        'lab_fee_paid',
        'entered_at'
    ]
    list_filter = ['status', 'lab_fee_paid']
    search_fields = ['lab_order__test_name', 'token__token_number']
    readonly_fields = ['entered_at', 'turnaround_minutes']


# ============================================================
# 9. LAB REPORT
# ============================================================
@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = [
        'lab_order',
        'is_same_day',
        'uploaded_by',
        'uploaded_at'
    ]
    list_filter = ['is_same_day']
    search_fields = ['lab_order__test_name', 'findings']


# ============================================================
# 10. PRESCRIPTION
# ============================================================
@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'medicine_name',
        'dosage',
        'frequency',
        'duration_days',
        'dispensed'
    ]
    list_filter = ['dispensed']
    search_fields = ['medicine_name', 'token__token_number', 'token__patient_name']


# ============================================================
# 11. PHARMACY QUEUE ENTRY
# ============================================================
@admin.register(PharmacyQueueEntry)
class PharmacyQueueEntryAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'status',
        'payment_collected',
        'total_bill',
        'entered_at'
    ]
    list_filter = ['status', 'payment_collected']
    search_fields = ['token__token_number', 'token__patient_name']


# ============================================================
# 12. PAYMENT
# ============================================================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'payment_type',
        'amount',
        'status',
        'paid_at'
    ]
    list_filter = ['payment_type', 'status']
    search_fields = ['token__token_number', 'reference_number']
    readonly_fields = ['paid_at']
    ordering = ['-paid_at']


# ============================================================
# 13. FOLLOWUP RULE (Admin Configurable)
# ============================================================
@admin.register(FollowupRule)
class FollowupRuleAdmin(admin.ModelAdmin):
    list_display = [
        'exempt_within_days',
        'is_active',
        'updated_by',
        'updated_at'
    ]
    list_filter = ['is_active']
    search_fields = ['updated_by__username']
    readonly_fields = ['updated_at']

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion of all rules
        return False


# ============================================================
# 14. DAILY ANALYTICS (Read-only)
# ============================================================
@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'doctor',
        'report_date',
        'total_tokens_issued',
        'avg_wait_minutes',
        'avg_consultation_minutes',
        'throttle_events_count'
    ]
    list_filter = ['report_date']
    search_fields = ['doctor__user__username']
    
    # FIX: Use a list or tuple instead of '__all__'
    readonly_fields = [
        'report_date',
        'doctor',
        'slot',
        'total_tokens_issued',
        'total_checkins',
        'total_no_shows',
        'avg_wait_minutes',
        'avg_consultation_minutes',
        'peak_queue_length',
        'peak_hour',
        'throttle_events_count',
        'computed_at'
    ]

# ============================================================
# Custom Admin Site Settings
# ============================================================
admin.site.site_header = "Smart OPD Administration"
admin.site.site_title = "Smart OPD"
admin.site.index_title = "Welcome to Smart OPD Management"