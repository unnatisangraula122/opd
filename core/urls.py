from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('slots/', views.available_slots, name='available-slots'),
    path('book/', views.book_token, name='book-token'),
]