# meters/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'models', views.MeterModelViewSet, basename='metermodel')
router.register(r'meters', views.MeterViewSet, basename='meter')
router.register(r'readings', views.ConsumptionReadingViewSet, basename='reading')

app_name = 'meters'

urlpatterns = [
    # Vistas HTML
    path('', views.dashboard_view, name='dashboard'),
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    
    # API REST
    path('api/', include(router.urls)),
    
    # API Pública (para sensores/dispositivos)
    path('api/public/reading/', views.create_reading_public, name='public_reading'),
    path('api/public/readings/bulk/', views.bulk_readings_public, name='public_bulk_readings'),
    
    # Utilidades
    path('api/import-csv/', views.import_csv, name='import_csv'),
]