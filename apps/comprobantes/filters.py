"""Filtros para la API de comprobantes usando django-filter."""
import django_filters
from .models import Comprobante


class ComprobanteFilter(django_filters.FilterSet):
    tipo = django_filters.ChoiceFilter(choices=Comprobante.TipoComprobante.choices)
    estado = django_filters.ChoiceFilter(choices=Comprobante.EstadoComprobante.choices)
    fecha_desde = django_filters.DateFilter(field_name='fecha_emision', lookup_expr='gte')
    fecha_hasta = django_filters.DateFilter(field_name='fecha_emision', lookup_expr='lte')
    ruc_cliente = django_filters.CharFilter(field_name='cliente__num_doc', lookup_expr='exact')
    cliente = django_filters.CharFilter(field_name='cliente__razon_social', lookup_expr='icontains')

    class Meta:
        model = Comprobante
        fields = ['tipo', 'estado', 'fecha_desde', 'fecha_hasta', 'ruc_cliente', 'cliente']
