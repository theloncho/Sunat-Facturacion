"""URL patterns web para Clientes."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_clientes_view, name='cliente-lista'),
    path('nuevo/', views.crear_cliente_view, name='cliente-crear'),
    path('<int:pk>/', views.detalle_cliente_view, name='cliente-detalle'),
    path('<int:pk>/editar/', views.editar_cliente_view, name='cliente-editar'),
    path('<int:pk>/eliminar/', views.eliminar_cliente_view, name='cliente-eliminar'),
    path('api/internal/consultar-doc/', views.consultar_documento_api, name='consultar-doc'),
]
