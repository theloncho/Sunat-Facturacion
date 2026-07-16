import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.empresa.models import Empresa, SerieComprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto


@pytest.mark.django_db
class TestComprobantesViewsAPIExtended(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='API Extended SAC', direccion='Lima'
        )
        SerieComprobante.objects.create(empresa=self.empresa, tipo='F', serie='F001', correlativo_actual=0)
        SerieComprobante.objects.create(empresa=self.empresa, tipo='B', serie='B001', correlativo_actual=0)
        
        self.user = CustomUser.objects.create_user(
            username='emisor_api', password='test123', rol='EMISOR', empresa=self.empresa
        )
        
        self.cliente = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente API SAC'
        )
        self.cliente_boleta = Cliente.objects.create(
            tipo_doc='DNI', num_doc='73182030', razon_social='Cliente Boleta'
        )
        
        self.producto = Producto.objects.create(
            codigo='PROD1', descripcion='Test Prod', unidad_medida='NIU',
            precio_unitario='100.00', afecto_igv=True
        )

    def test_emitir_factura_api(self):
        self.client.login(username='emisor_api', password='test123')
        data = {
            "cliente_id": self.cliente.id,
            "detalles": [
                {
                    "producto_id": self.producto.id,
                    "cantidad": 2,
                    "precio_unitario": "100.00",
                    "descuento": 0
                }
            ]
        }
        response = self.client.post(reverse('api-factura-create'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['serie'], 'F001')

    def test_emitir_boleta_api(self):
        self.client.login(username='emisor_api', password='test123')
        data = {
            "cliente_id": self.cliente_boleta.id,
            "detalles": [
                {
                    "producto_id": self.producto.id,
                    "cantidad": 1,
                    "precio_unitario": "100.00",
                    "descuento": 0
                }
            ]
        }
        response = self.client.post(reverse('api-boleta-create'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['serie'], 'B001')
