from django.contrib import admin
from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'precio_unitario', 'unidad_medida', 'afecto_igv', 'activo')
    search_fields = ('codigo', 'descripcion')
    list_filter = ('afecto_igv', 'activo', 'unidad_medida')
    list_editable = ('precio_unitario', 'afecto_igv', 'activo')
