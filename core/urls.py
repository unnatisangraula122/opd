from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
<<<<<<< HEAD
]
=======
    path('slots/', views.available_slots, name='available-slots'),
    path('book/', views.book_token, name='book-token'),
    path('search/', views.search_patient, name='search-patient'),
    path('check-in/<int:token_id>/', views.check_in_patient, name='check-in'),
    path('waiting-queue/', views.waiting_queue, name='waiting-queue-all'),
    path('waiting-queue/<int:doctor_id>/', views.waiting_queue, name='waiting-queue-doctor'),
     path('doctor-queue/<int:doctor_id>/', views.doctor_queue, name='doctor-queue'),
    path('start-consult/<int:token_id>/', views.start_consultation, name='start-consult'),
    path('complete-consult/<int:token_id>/', views.complete_consultation, name='complete-consult'),
    path('next-patient/<int:doctor_id>/', views.next_patient, name='next-patient'),
    
]   
>>>>>>> origin/main
