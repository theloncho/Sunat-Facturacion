"""URL patterns web para Empresa."""
from django.urls import path
from . import views_web

urlpatterns = [
    path('', views_web.lista_empresas_view, name='empresa-lista'),
    path('nueva/', views_web.crear_empresa_view, name='empresa-crear'),
    path('<int:pk>/', views_web.detalle_empresa_view, name='empresa-detalle'),
    path('<int:pk>/editar/', views_web.editar_empresa_view, name='empresa-editar'),
]
