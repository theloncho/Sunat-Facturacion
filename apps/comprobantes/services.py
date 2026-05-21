"""
Motor Tributario para el Sistema de Facturación Electrónica SUNAT.

Implementa los cálculos tributarios según normativa SUNAT:

Modelo Matemático:
  Base Imponible = Σ (cantidad_i × precio_unitario_i × (1 - descuento_i/100))
                   para productos afectos a IGV

  IGV = Base Imponible × 0.18

  Total Inafecto = Σ (cantidad_i × precio_unitario_i × (1 - descuento_i/100))
                   para productos NO afectos a IGV

  Total = Base Imponible + IGV + Total Inafecto

  Donde:
    - i representa cada línea de detalle del comprobante
    - La tasa de IGV es 18% (0.18) según normativa vigente
    - El descuento se aplica como porcentaje sobre el valor de venta
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.comprobantes.models import (
    Comprobante, DetalleComprobante, NotaCredito, LogEnvioSUNAT
)
from apps.empresa.models import SerieComprobante
from apps.clientes.models import Cliente


# ── Constantes tributarias ────────────────────────────────────────────
IGV_RATE = Decimal('0.18')
QUANTIZE_2 = Decimal('0.01')


class TributaryEngine:
    """
    Motor de cálculos tributarios para comprobantes electrónicos.

    Ecuaciones implementadas:
      1. valor_venta_i = cantidad_i × precio_unitario_i
      2. descuento_monto_i = valor_venta_i × (descuento_i / 100)
      3. subtotal_linea_i = valor_venta_i - descuento_monto_i
      4. igv_linea_i = subtotal_linea_i × 0.18  (si afecto_igv)
      5. Base Imponible = Σ subtotal_linea_i  (afectos)
      6. Total Inafecto = Σ subtotal_linea_i  (inafectos)
      7. IGV Total = Σ igv_linea_i
      8. Total = Base Imponible + IGV Total + Total Inafecto
    """

    @staticmethod
    def calcular_linea(cantidad, precio_unitario, descuento_pct, afecto_igv):
        """
        Calcula los montos de una línea de detalle individual.

        Args:
            cantidad: Cantidad del producto (Decimal).
            precio_unitario: Precio por unidad (Decimal).
            descuento_pct: Porcentaje de descuento 0-100 (Decimal).
            afecto_igv: Si el producto está afecto a IGV (bool).

        Returns:
            dict con: valor_venta, descuento_monto, subtotal, igv_linea, total_linea

        Ecuaciones:
            valor_venta = cantidad × precio_unitario
            descuento = valor_venta × (descuento_pct / 100)
            subtotal = valor_venta - descuento
            igv = subtotal × 0.18 (si afecto)
            total = subtotal + igv
        """
        cantidad = Decimal(str(cantidad))
        precio_unitario = Decimal(str(precio_unitario))
        descuento_pct = Decimal(str(descuento_pct))

        valor_venta = (cantidad * precio_unitario).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        descuento_monto = (valor_venta * descuento_pct / Decimal('100')).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        subtotal = (valor_venta - descuento_monto).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)

        if afecto_igv:
            igv_linea = (subtotal * IGV_RATE).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        else:
            igv_linea = Decimal('0.00')

        total_linea = subtotal + igv_linea

        return {
            'valor_venta': valor_venta,
            'descuento_monto': descuento_monto,
            'subtotal': subtotal,
            'igv_linea': igv_linea,
            'total_linea': total_linea,
        }

    @staticmethod
    def calcular_totales(detalles_data, productos_map):
        """
        Calcula los totales del comprobante a partir de sus líneas de detalle.

        Args:
            detalles_data: Lista de dicts con producto_id, cantidad, precio_unitario, descuento.
            productos_map: Dict {producto_id: producto_obj} para verificar afecto_igv.

        Returns:
            dict con: subtotal (base imponible), total_inafecto, igv, total, lineas[]

        Modelo Matemático:
            Base Imponible = Σ subtotal_i  (productos afectos)
            Total Inafecto = Σ subtotal_i  (productos inafectos)
            IGV = Σ igv_linea_i
            Total = Base Imponible + IGV + Total Inafecto
        """
        base_imponible = Decimal('0.00')
        total_inafecto = Decimal('0.00')
        total_igv = Decimal('0.00')
        lineas_calculadas = []

        for detalle in detalles_data:
            producto = productos_map[detalle['producto_id']]
            calculos = TributaryEngine.calcular_linea(
                cantidad=detalle['cantidad'],
                precio_unitario=detalle['precio_unitario'],
                descuento_pct=detalle.get('descuento', 0),
                afecto_igv=producto.afecto_igv,
            )

            if producto.afecto_igv:
                base_imponible += calculos['subtotal']
            else:
                total_inafecto += calculos['subtotal']

            total_igv += calculos['igv_linea']

            lineas_calculadas.append({
                **detalle,
                **calculos,
                'afecto_igv': producto.afecto_igv,
            })

        total = base_imponible + total_igv + total_inafecto

        return {
            'subtotal': base_imponible.quantize(QUANTIZE_2),
            'total_inafecto': total_inafecto.quantize(QUANTIZE_2),
            'igv': total_igv.quantize(QUANTIZE_2),
            'total': total.quantize(QUANTIZE_2),
            'lineas': lineas_calculadas,
        }


def validar_cliente_para_tipo(cliente, tipo_comprobante):
    """
    Valida que el tipo de documento del cliente sea compatible con el tipo de comprobante.

    Reglas SUNAT:
      - Factura: requiere RUC (11 dígitos)
      - Boleta: acepta DNI, CE o RUC
      - Nota de Crédito: según el comprobante original
    """
    if tipo_comprobante == Comprobante.TipoComprobante.FACTURA:
        if cliente.tipo_doc != Cliente.TipoDocumento.RUC:
            raise ValidationError(
                'Para emitir una Factura, el cliente debe tener RUC (11 dígitos).'
            )
    elif tipo_comprobante == Comprobante.TipoComprobante.BOLETA:
        if cliente.tipo_doc not in [Cliente.TipoDocumento.DNI, Cliente.TipoDocumento.CE, Cliente.TipoDocumento.RUC]:
            raise ValidationError(
                'Para emitir una Boleta, el cliente debe tener DNI, CE o RUC.'
            )


TRANSICIONES_VALIDAS = {
    Comprobante.EstadoComprobante.BORRADOR: [Comprobante.EstadoComprobante.EMITIDO],
    Comprobante.EstadoComprobante.EMITIDO: [Comprobante.EstadoComprobante.ENVIADO],
    Comprobante.EstadoComprobante.ENVIADO: [
        Comprobante.EstadoComprobante.ACEPTADO,
        Comprobante.EstadoComprobante.RECHAZADO,
    ],
    Comprobante.EstadoComprobante.RECHAZADO: [Comprobante.EstadoComprobante.ENVIADO],
    Comprobante.EstadoComprobante.ACEPTADO: [],
}


def transicionar_estado(comprobante, nuevo_estado):
    """
    Transiciona el estado de un comprobante según el flujo definido.

    Flujo válido:
      BORRADOR → EMITIDO → ENVIADO → ACEPTADO / RECHAZADO
      RECHAZADO → ENVIADO (para reenvío)

    Raises:
        ValidationError si la transición no es válida.
    """
    estados_permitidos = TRANSICIONES_VALIDAS.get(comprobante.estado, [])
    if nuevo_estado not in estados_permitidos:
        raise ValidationError(
            f'No se puede cambiar de {comprobante.get_estado_display()} '
            f'a {nuevo_estado}. Transiciones válidas: '
            f'{", ".join(estados_permitidos) or "ninguna"}.'
        )
    comprobante.estado = nuevo_estado
    comprobante.save(update_fields=['estado', 'updated_at'])
    return comprobante


@transaction.atomic
def generar_numero_correlativo(empresa, tipo_comprobante, comprobante_ref=None):
    """
    Genera el siguiente número correlativo para una serie de comprobante.
    Usa select_for_update() para evitar condiciones de carrera y garantizar
    que no haya saltos en la numeración.

    Returns:
        tuple (serie_str, numero_int)
    """
    from apps.empresa.models import SerieComprobante
    
    tipo_map = {
        Comprobante.TipoComprobante.FACTURA: SerieComprobante.TipoComprobante.FACTURA,
        Comprobante.TipoComprobante.BOLETA: SerieComprobante.TipoComprobante.BOLETA,
    }
    
    if tipo_comprobante == Comprobante.TipoComprobante.NOTA_CREDITO:
        if comprobante_ref and comprobante_ref.tipo == Comprobante.TipoComprobante.BOLETA:
            serie_tipo = SerieComprobante.TipoComprobante.NOTA_CREDITO_BOLETA
        else:
            serie_tipo = SerieComprobante.TipoComprobante.NOTA_CREDITO
    else:
        serie_tipo = tipo_map[tipo_comprobante]

    serie = (
        SerieComprobante.objects
        .select_for_update()
        .filter(empresa=empresa, tipo=serie_tipo)
        .first()
    )

    if not serie:
        raise ValidationError(
            f'No existe una serie configurada para {tipo_comprobante} en la empresa {empresa}.'
        )

    numero = serie.siguiente_correlativo()
    return serie.serie, numero


@transaction.atomic
def emitir_comprobante(empresa, cliente, tipo, detalles_data, usuario, auto_enviar=True):
    """
    Emite un comprobante electrónico completo.

    Pasos:
      1. Validar cliente para el tipo de comprobante
      2. Generar número correlativo
      3. Calcular totales tributarios
      4. Crear comprobante y detalles
      5. Generar XML mock
      6. Enviar al OSE (mock) si auto_enviar=True

    Returns:
        Comprobante creado
    """
    from apps.comprobantes.xml_generator import generar_xml_comprobante
    from apps.comprobantes.sunat_client import enviar_a_ose

    from apps.productos.models import Producto

    # 1. Validar cliente
    validar_cliente_para_tipo(cliente, tipo)

    # 2. Generar número correlativo atómico
    serie, numero = generar_numero_correlativo(empresa, tipo)

    # 3. Obtener productos y calcular totales
    producto_ids = [d['producto_id'] for d in detalles_data]
    productos = Producto.objects.filter(id__in=producto_ids)
    productos_map = {p.id: p for p in productos}

    if len(productos_map) != len(producto_ids):
        raise ValidationError('Uno o más productos no existen.')

    engine = TributaryEngine()
    totales = engine.calcular_totales(detalles_data, productos_map)

    # 4. Crear comprobante
    comprobante = Comprobante.objects.create(
        serie=serie,
        numero=numero,
        tipo=tipo,
        cliente=cliente,
        empresa=empresa,
        created_by=usuario,
        subtotal=totales['subtotal'],
        total_inafecto=totales['total_inafecto'],
        igv=totales['igv'],
        total=totales['total'],
        estado=Comprobante.EstadoComprobante.BORRADOR,
    )

    # Crear detalles
    for linea in totales['lineas']:
        DetalleComprobante.objects.create(
            comprobante=comprobante,
            producto=productos_map[linea['producto_id']],
            cantidad=linea['cantidad'],
            precio_unitario=linea['precio_unitario'],
            descuento=linea.get('descuento', 0),
            igv_linea=linea['igv_linea'],
            subtotal=linea['subtotal'],
        )

    # 5. Generar XML y transicionar a EMITIDO
    xml_content, hash_cpe = generar_xml_comprobante(comprobante)
    comprobante.xml_firmado = xml_content
    comprobante.hash_cpe = hash_cpe
    comprobante.estado = Comprobante.EstadoComprobante.EMITIDO
    comprobante.save(update_fields=['xml_firmado', 'hash_cpe', 'estado', 'updated_at'])

    # 6. Enviar al OSE (mock)
    if auto_enviar:
        enviar_a_ose(comprobante)

    return comprobante


@transaction.atomic
def emitir_nota_credito(empresa, comprobante_ref, motivo, tipo_nota, monto_afectado, usuario):
    """
    Emite una nota de crédito referenciando un comprobante original.

    Validaciones:
      - El monto afectado no puede superar el total del original.
      - El comprobante original debe estar ACEPTADO o EMITIDO.

    Returns:
        tuple (comprobante_nc, nota_credito)
    """
    from apps.comprobantes.xml_generator import generar_xml_comprobante
    from apps.comprobantes.sunat_client import enviar_a_ose

    monto_afectado = Decimal(str(monto_afectado))

    if monto_afectado > comprobante_ref.total:
        raise ValidationError(
            f'El monto afectado (S/.{monto_afectado}) no puede superar '
            f'el total del comprobante original (S/.{comprobante_ref.total}).'
        )

    if comprobante_ref.estado not in [
        Comprobante.EstadoComprobante.ACEPTADO,
        Comprobante.EstadoComprobante.EMITIDO,
    ]:
        raise ValidationError(
            'Solo se pueden emitir notas de crédito para comprobantes ACEPTADOS o EMITIDOS.'
        )

    # Generar número correlativo para la nota de crédito
    serie, numero = generar_numero_correlativo(
        empresa, 
        Comprobante.TipoComprobante.NOTA_CREDITO, 
        comprobante_ref=comprobante_ref
    )

    # Calcular IGV proporcional de la NC
    if comprobante_ref.subtotal > 0:
        proporcion = monto_afectado / (comprobante_ref.subtotal + comprobante_ref.total_inafecto + comprobante_ref.igv)
    else:
        proporcion = Decimal('1.00')

    igv_nc = (comprobante_ref.igv * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
    subtotal_nc = (monto_afectado - igv_nc).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)

    # Crear comprobante NC
    comprobante_nc = Comprobante.objects.create(
        serie=serie,
        numero=numero,
        tipo=Comprobante.TipoComprobante.NOTA_CREDITO,
        cliente=comprobante_ref.cliente,
        empresa=empresa,
        created_by=usuario,
        subtotal=subtotal_nc,
        igv=igv_nc,
        total=monto_afectado,
        estado=Comprobante.EstadoComprobante.EMITIDO,
    )

    # Crear registro NC
    nota_credito = NotaCredito.objects.create(
        comprobante_nota=comprobante_nc,
        comprobante_referencia=comprobante_ref,
        motivo=motivo,
        tipo_nota=tipo_nota,
        monto_afectado=monto_afectado,
    )

    # Clonar los detalles del comprobante original proporcionalmente
    from apps.comprobantes.models import DetalleComprobante
    
    detalles_nuevos = []
    for det_ref in comprobante_ref.detalles.all():
        nueva_cantidad = det_ref.cantidad * proporcion
        nuevo_igv_linea = (det_ref.igv_linea * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        nuevo_subtotal = (det_ref.subtotal * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        
        detalles_nuevos.append(
            DetalleComprobante(
                comprobante=comprobante_nc,
                producto=det_ref.producto,
                cantidad=nueva_cantidad.quantize(Decimal('.01'), rounding=ROUND_HALF_UP),
                precio_unitario=det_ref.precio_unitario,
                descuento=det_ref.descuento,
                igv_linea=nuevo_igv_linea,
                subtotal=nuevo_subtotal
            )
        )
    DetalleComprobante.objects.bulk_create(detalles_nuevos)


    # Generar XML y enviar
    xml_content, hash_cpe = generar_xml_comprobante(comprobante_nc)
    comprobante_nc.xml_firmado = xml_content
    comprobante_nc.hash_cpe = hash_cpe
    comprobante_nc.save(update_fields=['xml_firmado', 'hash_cpe', 'updated_at'])

    enviar_a_ose(comprobante_nc)

    return comprobante_nc, nota_credito
