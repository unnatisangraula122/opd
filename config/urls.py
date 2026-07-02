from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
import os

def serve_frontend(request):
    """Serve the main entry point (Today.html)"""
    
    # Map URL paths to HTML files
    path_map = {
        '': 'Today.html',
        'patient': 'patient/patient-dashboard.html',
        'doctor': 'doctor/doctor-dashboard.html',
        'reception': 'reception/reception-dashboard.html',
        'admin': 'admin/admin-dashboard.html',
        'lab': 'lab/lab-dashboard.html',
        'pharmacy': 'pharmacy/pharmacy-dashboard.html',
    }
    
    # Get the path from URL (remove leading/trailing slashes)
    url_path = request.path.strip('/')
    
    # Find the corresponding file
    filename = path_map.get(url_path, 'Today.html')
    
    html_path = os.path.join(settings.BASE_DIR, 'frontend', filename)
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Replace API base URL in HTML/JS if needed
            return HttpResponse(content)
    except FileNotFoundError:
        # List all files in frontend to help debug
        files = []
        for root, dirs, filenames in os.walk(os.path.join(settings.BASE_DIR, 'frontend')):
            for f in filenames:
                if f.endswith('.html'):
                    files.append(f"<li>{os.path.relpath(os.path.join(root, f), os.path.join(settings.BASE_DIR, 'frontend'))}</li>")
        
        return HttpResponse(f"""
            <h1>404: File not found</h1>
            <p>Tried to open: {filename}</p>
            <p>Available HTML files:</p>
            <ul>{''.join(files)}</ul>
        """)

def serve_static_files(request):
    """Serve CSS, JS files"""
    file_path = request.path.lstrip('/')
    full_path = os.path.join(settings.BASE_DIR, 'frontend', file_path)
    
    try:
        with open(full_path, 'rb') as f:
            return HttpResponse(f.read(), content_type=get_content_type(full_path))
    except FileNotFoundError:
        return HttpResponse(status=404)

def get_content_type(file_path):
    """Determine content type based on file extension"""
    if file_path.endswith('.css'):
        return 'text/css'
    elif file_path.endswith('.js'):
        return 'application/javascript'
    elif file_path.endswith('.png'):
        return 'image/png'
    elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
        return 'image/jpeg'
    elif file_path.endswith('.svg'):
        return 'image/svg+xml'
    return 'text/plain'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
    
    # Serve frontend pages
    path('', serve_frontend, name='home'),
    path('patient/', serve_frontend, name='patient'),
    path('doctor/', serve_frontend, name='doctor'),
    path('reception/', serve_frontend, name='reception'),
    path('admin-dashboard/', serve_frontend, name='admin-dashboard'),
    path('lab/', serve_frontend, name='lab'),
    path('pharmacy/', serve_frontend, name='pharmacy'),
    
    # Serve static files (CSS, JS)
    path('css/<path:filename>', serve_static_files, name='css'),
    path('js/<path:filename>', serve_static_files, name='js'),
]