"""
Tests del Motor Tributario — Cálculos de IGV, numeración y validaciones.
Cobertura de las reglas de negocio críticas del sistema SUNAT.
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.comprobantes.services import TributaryEngine, validar_cliente_para_tipo, transicionar_estado
from apps.comprobantes.models import Comprobante, DetalleComprobante, NotaCredito
from apps.empresa.models import Empresa, SerieComprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto


@pytest.mark.django_db
class TestTributaryEngine(TestCase):
    """Tests del motor de cálculos tributarios."""

    def test_calcular_linea_afecto_igv(self):
        """
        Verifica: subtotal = cantidad × precio × (1 - desc%)
                  igv = subtotal × 0.18
        """
        result = TributaryEngine.calcular_linea(
            cantidad=10, precio_unitario=100, descuento_pct=0, afecto_igv=True
        )
        self.assertEqual(result['subtotal'], Decimal('1000.00'))
        self.assertEqual(result['igv_linea'], Decimal('180.00'))
        self.assertEqual(result['total_linea'], Decimal('1180.00'))

    def test_calcular_linea_inafecto(self):
        """Producto inafecto: IGV debe ser 0."""
        result = TributaryEngine.calcular_linea(
            cantidad=5, precio_unitario=50, descuento_pct=0, afecto_igv=False
        )
        self.assertEqual(result['subtotal'], Decimal('250.00'))
        self.assertEqual(result['igv_linea'], Decimal('0.00'))

    def test_calcular_linea_con_descuento(self):
        """Verifica descuento: subtotal = 10 × 100 × (1 - 10/100) = 900."""
        result = TributaryEngine.calcular_linea(
            cantidad=10, precio_unitario=100, descuento_pct=10, afecto_igv=True
        )
        self.assertEqual(result['subtotal'], Decimal('900.00'))
        self.assertEqual(result['igv_linea'], Decimal('162.00'))

    def test_calcular_totales(self):
        """Test cálculo completo de un comprobante con múltiples líneas."""
        producto_afecto = Producto(id=1, afecto_igv=True)
        producto_inafecto = Producto(id=2, afecto_igv=False)
        productos_map = {1: producto_afecto, 2: producto_inafecto}

        detalles = [
            {'producto_id': 1, 'cantidad': 10, 'precio_unitario': 100, 'descuento': 0},
            {'producto_id': 2, 'cantidad': 5, 'precio_unitario': 50, 'descuento': 0},
        ]

        result = TributaryEngine.calcular_totales(detalles, productos_map)
        self.assertEqual(result['subtotal'], Decimal('1000.00'))      # Base imponible (afecto)
        self.assertEqual(result['total_inafecto'], Decimal('250.00'))  # Inafecto
        self.assertEqual(result['igv'], Decimal('180.00'))             # IGV solo afecto
        self.assertEqual(result['total'], Decimal('1430.00'))          # 1000 + 180 + 250


@pytest.mark.django_db
class TestValidaciones(TestCase):
    """Tests de validaciones de negocio."""

    def setUp(self):
        self.cliente_ruc = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20123456789',
            razon_social='Empresa Test SAC'
        )
        self.cliente_dni = Cliente.objects.create(
            tipo_doc='DNI', num_doc='12345678',
            razon_social='Juan Pérez'
        )

    def test_factura_requiere_ruc(self):
        """Factura solo acepta clientes con RUC."""
        # Debe funcionar con RUC
        validar_cliente_para_tipo(self.cliente_ruc, Comprobante.TipoComprobante.FACTURA)

        # Debe fallar con DNI
        with self.assertRaises(ValidationError):
            validar_cliente_para_tipo(self.cliente_dni, Comprobante.TipoComprobante.FACTURA)

    def test_boleta_acepta_dni(self):
        """Boleta acepta DNI, CE y RUC."""
        validar_cliente_para_tipo(self.cliente_dni, Comprobante.TipoComprobante.BOLETA)
        validar_cliente_para_tipo(self.cliente_ruc, Comprobante.TipoComprobante.BOLETA)

    def test_ruc_debe_tener_11_digitos(self):
        """Validación: RUC requiere exactamente 11 dígitos."""
        with self.assertRaises(ValidationError):
            Cliente.objects.create(tipo_doc='RUC', num_doc='123', razon_social='Test')

    def test_dni_debe_tener_8_digitos(self):
        """Validación: DNI requiere exactamente 8 dígitos."""
        with self.assertRaises(ValidationError):
            Cliente.objects.create(tipo_doc='DNI', num_doc='123', razon_social='Test')


@pytest.mark.django_db
class TestTransicionesEstado(TestCase):
    """Tests del flujo de estados de comprobantes."""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='Test SAC', direccion='Lima'
        )
        self.cliente = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente Test'
        )
        self.comprobante = Comprobante.objects.create(
            serie='F001', numero=1, tipo='FACTURA',
            cliente=self.cliente, empresa=self.empresa,
            subtotal=1000, igv=180, total=1180,
            estado=Comprobante.EstadoComprobante.BORRADOR,
        )

    def test_borrador_a_emitido(self):
        transicionar_estado(self.comprobante, Comprobante.EstadoComprobante.EMITIDO)
        self.assertEqual(self.comprobante.estado, 'EMITIDO')

    def test_emitido_a_enviado(self):
        self.comprobante.estado = 'EMITIDO'
        self.comprobante.save()
        transicionar_estado(self.comprobante, Comprobante.EstadoComprobante.ENVIADO)
        self.assertEqual(self.comprobante.estado, 'ENVIADO')

    def test_enviado_a_aceptado(self):
        self.comprobante.estado = 'ENVIADO'
        self.comprobante.save()
        transicionar_estado(self.comprobante, Comprobante.EstadoComprobante.ACEPTADO)
        self.assertEqual(self.comprobante.estado, 'ACEPTADO')

    def test_transicion_invalida(self):
        """No se puede ir de BORRADOR a ACEPTADO directamente."""
        with self.assertRaises(ValidationError):
            transicionar_estado(self.comprobante, Comprobante.EstadoComprobante.ACEPTADO)

    def test_aceptado_no_se_puede_eliminar(self):
        """Comprobante ACEPTADO no se puede eliminar."""
        self.comprobante.estado = 'ACEPTADO'
        self.comprobante.save()
        with self.assertRaises(ValidationError):
            self.comprobante.delete()

    def test_rechazado_puede_reenviarse(self):
        """RECHAZADO → ENVIADO es válido para reenvío."""
        self.comprobante.estado = 'RECHAZADO'
        self.comprobante.save()
        transicionar_estado(self.comprobante, Comprobante.EstadoComprobante.ENVIADO)
        self.assertEqual(self.comprobante.estado, 'ENVIADO')


@pytest.mark.django_db
class TestNotaCredito(TestCase):
    """Tests de validaciones de Nota de Crédito."""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='Test SAC', direccion='Lima'
        )
        self.cliente = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente Test'
        )
        self.comprobante_ref = Comprobante.objects.create(
            serie='F001', numero=1, tipo='FACTURA',
            cliente=self.cliente, empresa=self.empresa,
            subtotal=1000, igv=180, total=1180,
            estado='ACEPTADO',
        )

    def test_nota_credito_monto_no_supera_original(self):
        """El monto de la NC no puede superar el total del original."""
        nc = NotaCredito(
            comprobante_nota=Comprobante.objects.create(
                serie='FC01', numero=1, tipo='NOTA_CREDITO',
                cliente=self.cliente, empresa=self.empresa,
                subtotal=100, igv=18, total=118, estado='EMITIDO',
            ),
            comprobante_referencia=self.comprobante_ref,
            motivo='Test',
            tipo_nota='01',
            monto_afectado=Decimal('2000.00'),  # Más que el total (1180)
        )
        with self.assertRaises(ValidationError):
            nc.clean()


@pytest.mark.django_db
class TestNumeracionCorrelativa(TestCase):
    """Tests de numeración correlativa sin saltos."""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='Test SAC', direccion='Lima'
        )
        self.serie = SerieComprobante.objects.create(
            empresa=self.empresa, tipo='F', serie='F001', correlativo_actual=0
        )

    def test_correlativo_secuencial(self):
        """Los correlativos deben ser consecutivos sin saltos."""
        n1 = self.serie.siguiente_correlativo()
        n2 = self.serie.siguiente_correlativo()
        n3 = self.serie.siguiente_correlativo()
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 2)
        self.assertEqual(n3, 3)

    def test_unique_serie_numero(self):
        """No puede haber dos comprobantes con la misma serie-número."""
        cliente = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Test'
        )
        Comprobante.objects.create(
            serie='F001', numero=1, tipo='FACTURA',
            cliente=cliente, empresa=self.empresa,
            subtotal=100, igv=18, total=118,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Comprobante.objects.create(
                serie='F001', numero=1, tipo='FACTURA',
                cliente=cliente, empresa=self.empresa,
                subtotal=200, igv=36, total=236,
            )
