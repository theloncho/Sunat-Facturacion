"""URL patterns API para Reportes."""
from django.urls import path
from .views_api import LibroVentasAPIView

urlpatterns = [
    path('reportes/ventas-por-periodo/', LibroVentasAPIView.as_view(), name='api-libro-ventas'),
]
