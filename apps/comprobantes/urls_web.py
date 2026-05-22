"""URL patterns web para comprobantes."""
from django.urls import path
from . import views_web

urlpatterns = [
    path('', views_web.dashboard_view, name='dashboard'),
    path('comprobantes/emitir/', views_web.emitir_comprobante_view, name='comprobante-emitir'),
    path('comprobantes/', views_web.lista_comprobantes_view, name='comprobante-lista'),
    path('comprobantes/<int:pk>/', views_web.detalle_comprobante_view, name='comprobante-detalle'),
    path('comprobantes/<int:pk>/pdf/', views_web.pdf_comprobante_view, name='comprobante-pdf'),
    path('comprobantes/<int:pk>/xml/', views_web.descargar_xml_view, name='comprobante-xml'),
    path('comprobantes/<int:pk>/reenviar/', views_web.reenviar_comprobante_view, name='comprobante-reenviar'),
    path('comprobantes/nota-credito/', views_web.nota_credito_view, name='nota-credito'),
    # Internal search APIs
    path('api/internal/buscar-cliente/', views_web.buscar_cliente_api, name='buscar-cliente'),
    path('api/internal/buscar-comprobante/', views_web.buscar_comprobante_api, name='buscar-comprobante'),
]
