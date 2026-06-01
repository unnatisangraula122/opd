from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('slots/', views.available_slots, name='available-slots'),
    path('book/', views.book_token, name='book-token'),
    path('search/', views.search_patient, name='search-patient'),
    path('check-in/<int:token_id>/', views.check_in_patient, name='check-in'),
    path('waiting-queue/', views.waiting_queue, name='waiting-queue-all'),
    path('waiting-queue/<int:doctor_id>/', views.waiting_queue, name='waiting-queue-doctor'),
]