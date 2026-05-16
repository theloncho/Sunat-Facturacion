from django.contrib import admin
from .models import Empresa, SerieComprobante


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('ruc', 'razon_social', 'nombre_comercial', 'regimen_tributario')
    search_fields = ('ruc', 'razon_social')
    list_filter = ('regimen_tributario',)


@admin.register(SerieComprobante)
class SerieComprobanteAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'tipo', 'serie', 'correlativo_actual')
    list_filter = ('tipo', 'empresa')
    search_fields = ('serie',)
