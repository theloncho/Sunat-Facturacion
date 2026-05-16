from django.contrib import admin
from .models import Comprobante, DetalleComprobante, NotaCredito, LogEnvioSUNAT


class DetalleComprobanteInline(admin.TabularInline):
    model = DetalleComprobante
    extra = 0
    readonly_fields = ('igv_linea', 'subtotal')


class LogEnvioSUNATInline(admin.TabularInline):
    model = LogEnvioSUNAT
    extra = 0
    readonly_fields = ('fecha_envio', 'estado_respuesta', 'codigo_respuesta', 'descripcion')


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ('serie_numero', 'tipo', 'cliente', 'total', 'estado', 'fecha_emision')
    list_filter = ('tipo', 'estado', 'fecha_emision', 'empresa')
    search_fields = ('serie', 'numero', 'cliente__razon_social', 'cliente__num_doc')
    readonly_fields = ('subtotal', 'igv', 'total', 'xml_firmado', 'hash_cpe')
    inlines = [DetalleComprobanteInline, LogEnvioSUNATInline]
    date_hierarchy = 'fecha_emision'


@admin.register(NotaCredito)
class NotaCreditoAdmin(admin.ModelAdmin):
    list_display = ('comprobante_nota', 'comprobante_referencia', 'tipo_nota', 'monto_afectado')
    list_filter = ('tipo_nota',)


@admin.register(LogEnvioSUNAT)
class LogEnvioSUNATAdmin(admin.ModelAdmin):
    list_display = ('comprobante', 'fecha_envio', 'estado_respuesta', 'codigo_respuesta')
    list_filter = ('estado_respuesta',)
    date_hierarchy = 'fecha_envio'
