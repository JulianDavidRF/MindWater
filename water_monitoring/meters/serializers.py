# meters/serializers.py

from rest_framework import serializers
from .models import MeterModel, Meter, ConsumptionReading


class MeterModelSerializer(serializers.ModelSerializer):
    meter_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MeterModel
        fields = ['id', 'name', 'manufacturer', 'liters_per_unit', 'description', 
                  'meter_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_meter_count(self, obj):
        return obj.meters.filter(is_active=True).count()


class ConsumptionReadingSerializer(serializers.ModelSerializer):
    consumption_info = serializers.SerializerMethodField()
    liters = serializers.SerializerMethodField()
    
    class Meta:
        model = ConsumptionReading
        fields = ['id', 'meter', 'accumulated_value', 'timestamp', 'liters', 
                  'consumption_info', 'created_at']
        read_only_fields = ['created_at']
    
    def get_liters(self, obj):
        """Calcula litros totales acumulados"""
        return round(float(obj.accumulated_value) * float(obj.meter.model.liters_per_unit), 2)
    
    def get_consumption_info(self, obj):
        return obj.get_consumption_since_last()


class ConsumptionReadingCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear lecturas"""
    meter_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = ConsumptionReading
        fields = ['meter_id', 'accumulated_value', 'timestamp']
    
    def validate_meter_id(self, value):
        try:
            meter = Meter.objects.get(meter_id=value, is_active=True)
            return meter
        except Meter.DoesNotExist:
            raise serializers.ValidationError(f"Contador con ID '{value}' no encontrado o inactivo")
    
    def create(self, validated_data):
        meter = validated_data.pop('meter_id')
        validated_data['meter'] = meter
        return super().create(validated_data)


class BulkReadingSerializer(serializers.Serializer):
    """Serializer para importación masiva de lecturas"""
    readings = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=1000
    )
    
    def validate_readings(self, value):
        errors = []
        for idx, reading in enumerate(value):
            if 'meter_id' not in reading:
                errors.append(f"Lectura {idx}: falta 'meter_id'")
            if 'accumulated_value' not in reading:
                errors.append(f"Lectura {idx}: falta 'accumulated_value'")
            if 'timestamp' not in reading:
                errors.append(f"Lectura {idx}: falta 'timestamp'")
        
        if errors:
            raise serializers.ValidationError(errors)
        return value


class MeterSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True)
    liters_per_unit = serializers.DecimalField(
        source='model.liters_per_unit', 
        max_digits=10, 
        decimal_places=4, 
        read_only=True
    )
    last_reading = serializers.SerializerMethodField()
    consumption_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Meter
        fields = ['id', 'meter_id', 'model', 'model_name', 'liters_per_unit',
                  'latitude', 'longitude', 'installation_date', 'address', 
                  'notes', 'is_active', 'last_reading', 'consumption_stats',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_last_reading(self, obj):
        last = obj.get_last_reading()
        if last:
            return {
                'accumulated_value': float(last.accumulated_value),
                'timestamp': last.timestamp,
                'liters': round(float(last.accumulated_value) * float(obj.model.liters_per_unit), 2)
            }
        return None
    
    def get_consumption_stats(self, obj):
        return obj.get_consumption_stats(days=30)


class MeterCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear contadores con lat/lon"""
    
    class Meta:
        model = Meter
        fields = ['meter_id', 'model', 'latitude', 'longitude', 
                  'installation_date', 'address', 'notes', 'is_active']


class MeterGeoJSONSerializer(serializers.ModelSerializer):
    """Serializer GeoJSON para el mapa"""
    last_reading = serializers.SerializerMethodField()
    model_name = serializers.CharField(source='model.name', read_only=True)
    liters_per_unit = serializers.DecimalField(
        source='model.liters_per_unit',
        max_digits=10,
        decimal_places=4,
        read_only=True
    )
    
    class Meta:
        model = Meter
        fields = ['id', 'meter_id', 'model_name', 'address', 'is_active', 
                  'latitude', 'longitude', 'last_reading', 'liters_per_unit']
    
    def get_last_reading(self, obj):
        last = obj.get_last_reading()
        if last:
            consumption = last.get_consumption_since_last()
            liters = round(float(last.accumulated_value) * float(obj.model.liters_per_unit), 2)
            
            return {
                'accumulated_value': float(last.accumulated_value),
                'timestamp': last.timestamp,
                'liters': liters,
                'consumption': consumption
            }
        return None