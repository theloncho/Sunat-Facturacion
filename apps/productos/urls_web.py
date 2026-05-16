"""URL patterns web para Productos."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_productos_view, name='producto-lista'),
    path('nuevo/', views.crear_producto_view, name='producto-crear'),
    path('importar/', views.importar_productos_excel_view, name='producto-importar'),
    path('<int:pk>/editar/', views.editar_producto_view, name='producto-editar'),
    path('<int:pk>/eliminar/', views.eliminar_producto_view, name='producto-eliminar'),
]
