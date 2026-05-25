from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home(request):
    return HttpResponse("""
        <h1>Smart OPD API is Running! 🚀</h1>
        <p>Try these URLs:</p>
        <ul>
            <li><a href='/api/core/health/'>Health Check</a></li>
            <li><a href='/admin/'>Admin Panel</a></li>
        </ul>
    """)

urlpatterns = [
    path('', home),  # This adds the homepage
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
]