# water_monitoring/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import custom admin logout to handle GET requests from the UI
from meters.views import admin_logout_view

urlpatterns = [
    # Custom logout that accepts GET/POST and redirects (prevents 405 on GET)
    path('admin/logout/', admin_logout_view),
    path('admin/', admin.site.urls),
    path('', include('meters.urls')),
]

# Configuración para servir archivos estáticos en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Personalización del admin
admin.site.site_header = "Water Monitoring System"
admin.site.site_title = "WMS Admin"
admin.site.index_title = "Panel de Administración"