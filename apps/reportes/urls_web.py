"""URL patterns web para Reportes."""
from django.urls import path
from . import views_web

urlpatterns = [
    path('libro-ventas/', views_web.libro_ventas_view, name='libro-ventas'),
    path('exportar-excel/', views_web.exportar_excel_view, name='exportar-excel'),
]
