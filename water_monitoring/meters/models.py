# meters/models.py

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class MeterModel(models.Model):
    """Modelo de contador - Define las características del tipo de contador"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del modelo"
    )
    manufacturer = models.CharField(
        max_length=100,
        verbose_name="Fabricante",
        blank=True
    )
    liters_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0.0001)],
        verbose_name="Litros por unidad",
        help_text="Factor de conversión: 1 unidad del contador = X litros"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Modelo de Contador"
        verbose_name_plural = "Modelos de Contadores"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.liters_per_unit} L/unidad)"


class Meter(models.Model):
    """Contador individual instalado en campo"""
    
    meter_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="ID del Contador",
        help_text="Identificador único del contador físico"
    )
    model = models.ForeignKey(
        MeterModel,
        on_delete=models.PROTECT,
        related_name='meters',
        verbose_name="Modelo"
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Latitud"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="Longitud"
    )
    installation_date = models.DateField(
        default=timezone.now,
        verbose_name="Fecha de instalación"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dirección"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contador"
        verbose_name_plural = "Contadores"
        ordering = ['meter_id']
    
    def __str__(self):
        return f"{self.meter_id} - {self.model.name}"
    
    def get_last_reading(self):
        """Obtiene la última lectura del contador"""
        return self.readings.order_by('-timestamp').first()
    
    def get_consumption_stats(self, days=30):
        """Calcula estadísticas de consumo para los últimos N días"""
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        
        cutoff_date = timezone.now() - timedelta(days=days)
        readings = self.readings.filter(timestamp__gte=cutoff_date).order_by('timestamp')
        
        if readings.count() < 2:
            return None
        
        first_reading = readings.first()
        last_reading = readings.last()
        
        total_units = float(last_reading.accumulated_value) - float(first_reading.accumulated_value)
        total_liters = total_units * float(self.model.liters_per_unit)
        
        # Calcular días reales transcurridos
        time_diff = last_reading.timestamp - first_reading.timestamp
        actual_days = max(time_diff.total_seconds() / 86400, 1)  # Mínimo 1 día
        
        return {
            'total_liters': round(total_liters, 2),
            'total_units': round(total_units, 2),
            'days': days,
            'actual_days': round(actual_days, 2),
            'avg_daily_liters': round(total_liters / actual_days, 2),
            'first_reading_date': first_reading.timestamp,
            'last_reading_date': last_reading.timestamp,
        }


class ConsumptionReading(models.Model):
    """Registro de lectura de consumo"""
    
    meter = models.ForeignKey(
        Meter,
        on_delete=models.CASCADE,
        related_name='readings',
        verbose_name="Contador"
    )
    accumulated_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Valor acumulado",
        help_text="Valor acumulado mostrado en el contador"
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora",
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Lectura de Consumo"
        verbose_name_plural = "Lecturas de Consumo"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['meter', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.meter.meter_id} - {self.accumulated_value} @ {self.timestamp}"
    
    def get_consumption_since_last(self):
        """Calcula el consumo desde la última lectura"""
        previous = ConsumptionReading.objects.filter(
            meter=self.meter,
            timestamp__lt=self.timestamp
        ).order_by('-timestamp').first()
        
        if not previous:
            return None
        
        units_consumed = float(self.accumulated_value - previous.accumulated_value)
        liters_consumed = units_consumed * float(self.meter.model.liters_per_unit)
        
        time_diff = self.timestamp - previous.timestamp
        hours = time_diff.total_seconds() / 3600
        
        return {
            'units': units_consumed,
            'liters': round(liters_consumed, 2),
            'hours': round(hours, 2),
            'liters_per_hour': round(liters_consumed / hours, 2) if hours > 0 else 0,
            'previous_reading': {
                'id': previous.id,
                'accumulated_value': float(previous.accumulated_value),
                'timestamp': previous.timestamp.isoformat()
            }
        }
    
    def save(self, *args, **kwargs):
        """Override save para validaciones adicionales"""
        # Validar que el valor acumulado no sea menor que lecturas anteriores
        if self.pk is None:  # Solo en creación
            last_reading = self.meter.get_last_reading()
            if last_reading and self.accumulated_value < last_reading.accumulated_value:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    f"El valor acumulado ({self.accumulated_value}) no puede ser menor "
                    f"que la última lectura ({last_reading.accumulated_value})"
                )
        super().save(*args, **kwargs)