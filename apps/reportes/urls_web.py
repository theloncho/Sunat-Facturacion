"""URL patterns web para Reportes."""
from django.urls import path
from . import views_web

urlpatterns = [
    path('libro-ventas/', views_web.libro_ventas_view, name='libro-ventas'),
    path('exportar-csv/', views_web.exportar_csv_view, name='exportar-csv'),
]
