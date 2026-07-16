import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.test import override_settings
from apps.accounts.models import CustomUser
from apps.empresa.models import Empresa, SerieComprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto
from apps.comprobantes.models import Comprobante


@pytest.mark.django_db
@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class TestComprobantesViewsWeb(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='Web Test SAC', direccion='Lima'
        )
        SerieComprobante.objects.create(empresa=self.empresa, tipo='F', serie='F001', correlativo_actual=0)
        
        self.user = CustomUser.objects.create_user(
            username='emisor_web', password='test123', rol='EMISOR', empresa=self.empresa
        )
        
        self.cliente = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente Web SAC'
        )
        
        self.producto = Producto.objects.create(
            codigo='PROD1', descripcion='Test Prod', unidad_medida='NIU',
            precio_unitario='100.00', afecto_igv=True
        )

    def test_dashboard_view(self):
        self.client.login(username='emisor_web', password='test123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_emitir_comprobante_view(self):
        self.client.login(username='emisor_web', password='test123')
        response = self.client.get(reverse('comprobante-emitir'))
        self.assertEqual(response.status_code, 200)

    def test_lista_comprobantes_view(self):
        self.client.login(username='emisor_web', password='test123')
        response = self.client.get(reverse('comprobante-lista'))
        self.assertEqual(response.status_code, 200)

    def test_emitir_nota_credito_view(self):
        self.client.login(username='emisor_web', password='test123')
        response = self.client.get(reverse('nota-credito'))
        self.assertEqual(response.status_code, 200)

    def test_libro_ventas_view(self):
        self.client.login(username='emisor_web', password='test123')
        response = self.client.get(reverse('libro-ventas'))
        self.assertEqual(response.status_code, 200)
