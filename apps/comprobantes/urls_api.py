"""URL patterns para la API REST de comprobantes."""
from django.urls import path
from . import views_api

urlpatterns = [
    path('facturas/', views_api.FacturaCreateView.as_view(), name='api-factura-create'),
    path('boletas/', views_api.BoletaCreateView.as_view(), name='api-boleta-create'),
    path('notas-credito/', views_api.NotaCreditoCreateView.as_view(), name='api-nc-create'),
    path('comprobantes/', views_api.ComprobanteListView.as_view(), name='api-comprobante-list'),
    path('comprobantes/<int:pk>/', views_api.ComprobanteDetailView.as_view(), name='api-comprobante-detail'),
    path('comprobantes/<int:pk>/reenviar/', views_api.ReenviarView.as_view(), name='api-comprobante-reenviar'),
    path('comprobantes/<int:pk>/pdf/', views_api.ComprobantePDFView.as_view(), name='api-comprobante-pdf'),
]
