from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
import os

# Read the HTML file
def serve_frontend(request):
    html_path = os.path.join(settings.BASE_DIR, 'frontend', 'index2.html')
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HttpResponse(html_content)
    except FileNotFoundError:
        return HttpResponse("<h1>Error: index2.html not found</h1><p>Make sure the file exists in the frontend folder</p>")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
    path('', serve_frontend, name='home'),
]