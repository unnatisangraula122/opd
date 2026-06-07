from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('slots/', views.available_slots, name='available-slots'),
    path('book/', views.book_token, name='book-token'),
    path('search/', views.search_patient, name='search-patient'),
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
]