# meters/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import MeterModel, Meter, ConsumptionReading


@admin.register(MeterModel)
class MeterModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'manufacturer', 'liters_per_unit', 'meter_count', 'created_at']
    search_fields = ['name', 'manufacturer']
    list_filter = ['manufacturer', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'manufacturer', 'liters_per_unit')
        }),
        ('Detalles', {
            'fields': ('description',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def meter_count(self, obj):
        count = obj.meters.count()
        url = reverse('admin:meters_meter_changelist') + f'?model__id__exact={obj.id}'
        return format_html('<a href="{}">{} contadores</a>', url, count)
    meter_count.short_description = 'Contadores'


@admin.register(Meter)
class MeterAdmin(admin.ModelAdmin):
    list_display = ['meter_id', 'model', 'address', 'is_active', 'last_reading_display', 'installation_date']
    list_filter = ['is_active', 'model', 'installation_date']
    search_fields = ['meter_id', 'address']
    readonly_fields = ['created_at', 'updated_at', 'last_reading_info']
    date_hierarchy = 'installation_date'
    
    fieldsets = (
        ('Identificación', {
            'fields': ('meter_id', 'model', 'is_active')
        }),
        ('Ubicación', {
            'fields': ('latitude', 'longitude', 'address')
        }),
        ('Información Adicional', {
            'fields': ('installation_date', 'notes')
        }),
        ('Última Lectura', {
            'fields': ('last_reading_info',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def last_reading_display(self, obj):
        last = obj.get_last_reading()
        if last:
            return f"{last.accumulated_value} ({last.timestamp.strftime('%Y-%m-%d %H:%M')})"
        return "Sin lecturas"
    last_reading_display.short_description = 'Última Lectura'
    
    def last_reading_info(self, obj):
        last = obj.get_last_reading()
        if not last:
            return "No hay lecturas registradas"
        
        consumption = last.get_consumption_since_last()
        html = f"""
        <div style="padding: 10px; background: #f8f9fa; border-radius: 5px;">
            <p><strong>Valor acumulado:</strong> {last.accumulated_value} unidades</p>
            <p><strong>Fecha:</strong> {last.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
        
        if consumption:
            html += f"""
            <hr>
            <p><strong>Consumo desde última lectura:</strong></p>
            <ul>
                <li>Unidades: {consumption['units']}</li>
                <li>Litros: {consumption['liters']} L</li>
                <li>Tiempo: {consumption['hours']} horas</li>
                <li>Tasa: {consumption['liters_per_hour']} L/h</li>
            </ul>
            """
        
        html += "</div>"
        return mark_safe(html)
    last_reading_info.short_description = 'Información de Última Lectura'


@admin.register(ConsumptionReading)
class ConsumptionReadingAdmin(admin.ModelAdmin):
    list_display = ['meter', 'accumulated_value', 'consumption_display', 'timestamp']
    list_filter = ['meter__model', 'timestamp']
    search_fields = ['meter__meter_id']
    readonly_fields = ['created_at', 'consumption_info']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Lectura', {
            'fields': ('meter', 'accumulated_value', 'timestamp')
        }),
        ('Análisis de Consumo', {
            'fields': ('consumption_info',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def consumption_display(self, obj):
        consumption = obj.get_consumption_since_last()
        if consumption:
            return f"{consumption['liters']} L ({consumption['liters_per_hour']} L/h)"
        return "Primera lectura"
    consumption_display.short_description = 'Consumo'
    
    def consumption_info(self, obj):
        consumption = obj.get_consumption_since_last()
        if not consumption:
            return "Esta es la primera lectura del contador"
        
        html = f"""
        <div style="padding: 10px; background: #f8f9fa; border-radius: 5px;">
            <h4>Consumo desde lectura anterior</h4>
            <p><strong>Unidades consumidas:</strong> {consumption['units']}</p>
            <p><strong>Litros consumidos:</strong> {consumption['liters']} L</p>
            <p><strong>Tiempo transcurrido:</strong> {consumption['hours']} horas</p>
            <p><strong>Tasa de consumo:</strong> {consumption['liters_per_hour']} L/h</p>
            <hr>
            <p><strong>Lectura anterior:</strong></p>
            <ul>
                <li>Valor: {consumption['previous_reading'].accumulated_value}</li>
                <li>Fecha: {consumption['previous_reading'].timestamp.strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
        </div>
        """
        return mark_safe(html)
    consumption_info.short_description = 'Información de Consumo'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('meter', 'meter__model')