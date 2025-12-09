# meters/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from datetime import datetime, timedelta
from django.utils import timezone
import csv
import io

from .models import MeterModel, Meter, ConsumptionReading
from .serializers import (
    MeterModelSerializer, MeterSerializer, MeterCreateSerializer,
    MeterGeoJSONSerializer, ConsumptionReadingSerializer,
    ConsumptionReadingCreateSerializer, BulkReadingSerializer
)


def admin_logout_view(request):
    """
    Logout view that accepts GET and POST and redirects to LOGOUT_REDIRECT_URL.
    This is provided to support UI links that perform a GET to /admin/logout/.
    """
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    from django.conf import settings
    from django.http import HttpResponseNotAllowed

    if request.method in ('GET', 'POST'):
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL or '/')
    return HttpResponseNotAllowed(['GET', 'POST'])


# ============= VISTAS HTML =============

@login_required
def dashboard_view(request):
    """Vista principal del dashboard con mapa"""
    meters = Meter.objects.filter(is_active=True).select_related('model')
    context = {
        'meters_count': meters.count(),
        'models_count': MeterModel.objects.count(),
    }
    return render(request, 'meters/dashboard.html', context)


@login_required
def admin_panel_view(request):
    """Vista del panel de administración"""
    return render(request, 'meters/admin_panel.html')


# ============= API VIEWSETS =============

class MeterModelViewSet(viewsets.ModelViewSet):
    """ViewSet para modelos de contadores"""
    queryset = MeterModel.objects.all()
    serializer_class = MeterModelSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def meters(self, request, pk=None):
        """Lista todos los contadores de este modelo"""
        model = self.get_object()
        meters = model.meters.filter(is_active=True)
        serializer = MeterSerializer(meters, many=True)
        return Response(serializer.data)


class MeterViewSet(viewsets.ModelViewSet):
    """ViewSet para contadores"""
    queryset = Meter.objects.select_related('model').filter(is_active=True)
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MeterCreateSerializer
        elif self.action == 'geojson':
            return MeterGeoJSONSerializer
        return MeterSerializer
    
    @action(detail=False, methods=['get'])
    def geojson(self, request):
        """Retorna todos los contadores en formato GeoJSON para el mapa"""
        meters = self.get_queryset()
        serializer = MeterGeoJSONSerializer(meters, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def readings(self, request, pk=None):
        """Obtiene lecturas de un contador específico"""
        meter = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        cutoff_date = timezone.now() - timedelta(days=days)
        readings = meter.readings.filter(timestamp__gte=cutoff_date).order_by('timestamp')
        
        serializer = ConsumptionReadingSerializer(readings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Obtiene estadísticas de consumo"""
        meter = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        stats = meter.get_consumption_stats(days=days)
        return Response(stats if stats else {})
    
    @action(detail=True, methods=['get'])
    def consumption_chart(self, request, pk=None):
        """Datos para gráfica de consumo diario"""
        meter = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        cutoff_date = timezone.now() - timedelta(days=days)
        readings = meter.readings.filter(timestamp__gte=cutoff_date).order_by('timestamp')
        
        chart_data = []
        previous = None
        
        for reading in readings:
            if previous:
                consumption = reading.get_consumption_since_last()
                if consumption:
                    chart_data.append({
                        'date': reading.timestamp.date().isoformat(),
                        'liters': consumption['liters'],
                        'hours': consumption['hours'],
                    })
            previous = reading
        
        return Response(chart_data)


class ConsumptionReadingViewSet(viewsets.ModelViewSet):
    """ViewSet para lecturas de consumo"""
    queryset = ConsumptionReading.objects.select_related('meter', 'meter__model')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ConsumptionReadingCreateSerializer
        return ConsumptionReadingSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        meter_id = self.request.query_params.get('meter_id')
        
        if meter_id:
            queryset = queryset.filter(meter__meter_id=meter_id)
        
        return queryset.order_by('-timestamp')


# ============= API ENDPOINTS PÚBLICOS (para sensores) =============

@api_view(['POST'])
@permission_classes([AllowAny])
def create_reading_public(request):
    """
    Endpoint público para registrar una lectura
    POST /api/public/reading/
    Body: {
        "meter_id": "MTR001",
        "accumulated_value": 12345.67,
        "timestamp": "2024-01-15T10:30:00Z"  # Opcional
    }
    """
    serializer = ConsumptionReadingCreateSerializer(data=request.data)
    if serializer.is_valid():
        reading = serializer.save()
        return Response({
            'success': True,
            'reading_id': reading.id,
            'meter_id': reading.meter.meter_id,
            'accumulated_value': float(reading.accumulated_value),
            'timestamp': reading.timestamp
        }, status=status.HTTP_201_CREATED)
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def bulk_readings_public(request):
    """
    Endpoint público para registrar múltiples lecturas
    POST /api/public/readings/bulk/
    Body: {
        "readings": [
            {
                "meter_id": "MTR001",
                "accumulated_value": 12345.67,
                "timestamp": "2024-01-15T10:30:00Z"
            },
            ...
        ]
    }
    """
    serializer = BulkReadingSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    readings_data = serializer.validated_data['readings']
    created = []
    errors = []
    
    for idx, reading_data in enumerate(readings_data):
        reading_serializer = ConsumptionReadingCreateSerializer(data=reading_data)
        if reading_serializer.is_valid():
            reading = reading_serializer.save()
            created.append({
                'index': idx,
                'reading_id': reading.id,
                'meter_id': reading.meter.meter_id
            })
        else:
            errors.append({
                'index': idx,
                'meter_id': reading_data.get('meter_id', 'unknown'),
                'errors': reading_serializer.errors
            })
    
    return Response({
        'success': len(errors) == 0,
        'created': len(created),
        'failed': len(errors),
        'created_readings': created,
        'errors': errors
    }, status=status.HTTP_201_CREATED if len(errors) == 0 else status.HTTP_207_MULTI_STATUS)


# ============= IMPORTACIÓN CSV =============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_csv(request):
    """
    Importa lecturas desde un archivo CSV
    CSV Format: meter_id,accumulated_value,timestamp
    Ejemplo: MTR001,12345.67,2024-01-15 10:30:00
    """
    if 'file' not in request.FILES:
        return Response({
            'success': False,
            'error': 'No se proporcionó archivo'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    csv_file = request.FILES['file']
    
    if not csv_file.name.endswith('.csv'):
        return Response({
            'success': False,
            'error': 'El archivo debe ser CSV'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created = []
        errors = []
        
        for idx, row in enumerate(reader, start=1):
            try:
                meter = Meter.objects.get(meter_id=row['meter_id'], is_active=True)
                
                # Parsear timestamp
                timestamp_str = row.get('timestamp', '')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = timezone.now()
                
                reading = ConsumptionReading.objects.create(
                    meter=meter,
                    accumulated_value=float(row['accumulated_value']),
                    timestamp=timestamp
                )
                created.append(reading.id)
                
            except Meter.DoesNotExist:
                errors.append(f"Fila {idx}: Contador '{row.get('meter_id')}' no encontrado")
            except KeyError as e:
                errors.append(f"Fila {idx}: Falta columna {str(e)}")
            except ValueError as e:
                errors.append(f"Fila {idx}: Error de valor - {str(e)}")
            except Exception as e:
                errors.append(f"Fila {idx}: {str(e)}")
        
        return Response({
            'success': len(errors) == 0,
            'created': len(created),
            'failed': len(errors),
            'errors': errors
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error procesando archivo: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)