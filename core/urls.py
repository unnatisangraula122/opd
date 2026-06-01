from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
<<<<<<< HEAD
=======
    path('slots/', views.available_slots, name='available-slots'),
    path('book/', views.book_token, name='book-token'),
>>>>>>> 5f1a79e6441ffa639ad7de7ee89fdaec0d4f60f7
]