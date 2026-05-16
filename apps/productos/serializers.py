"""Serializers y API views para Productos."""
from rest_framework import serializers, viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Producto


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['id', 'codigo', 'descripcion', 'unidad_medida', 'precio_unitario', 'afecto_igv', 'activo']


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.filter(activo=True)
    serializer_class = ProductoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['afecto_igv', 'unidad_medida']
    search_fields = ['codigo', 'descripcion']
