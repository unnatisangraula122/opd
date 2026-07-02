from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('slots/', views.available_slots, name='slots'),
    path('book/', views.book_token, name='book'),
    path('search/', views.search_patient, name='search'),
    path('check-in/<int:token_id>/', views.check_in_patient, name='check-in'),
    path('waiting-queue/', views.waiting_queue, name='waiting-queue'),
    path('waiting-queue/<int:doctor_id>/', views.waiting_queue, name='waiting-queue-doctor'),
    path('doctor-queue/<int:doctor_id>/', views.doctor_queue, name='doctor-queue'),
    path('start-consult/<int:token_id>/', views.start_consultation, name='start-consult'),
    path('complete-consult/<int:token_id>/', views.complete_consultation, name='complete-consult'),
    path('next-patient/<int:doctor_id>/', views.next_patient, name='next-patient'),
    path('patient/register/', views.patient_register, name='patient-register'),
    path('patient/login/', views.patient_login, name='patient-login'),
    path('patient/logout/', views.patient_logout, name='patient-logout'),
    path('patient/me/', views.get_current_patient, name='patient-me'),
    path('patient/tokens/', views.get_patient_tokens, name='patient-tokens'),
    path('followup/<int:token_id>/', views.create_followup, name='followup'),
    path('cancel/<int:token_id>/', views.cancel_token, name='cancel'),
    path('analytics/', views.analytics, name='analytics'),
     # ========== NEW URLs (add these) ==========
    
    # Consultation Notes (Doctor saves diagnosis)
    path('consultation-notes/<int:token_id>/', views.save_consultation_notes, name='consultation-notes'),
    
    # Lab Workflow
    path('lab/order/<int:token_id>/', views.create_lab_order, name='lab-order'),
    path('lab/queue/', views.lab_queue, name='lab-queue'),
    path('lab/complete/<int:lab_order_id>/', views.complete_lab_order, name='lab-complete'),
    
    # Pharmacy Workflow
    path('pharmacy/queue/', views.pharmacy_queue, name='pharmacy-queue'),
    
    # Payment
    path('payment/<int:token_id>/', views.create_payment, name='payment'),
    
    # Patient History (View all past visits)
    path('patient-history/<str:phone>/', views.patient_history, name='patient-history'),
]