"""
Mock OSE (Operador de Servicios Electrónicos) Client.
Simula el envío de comprobantes a SUNAT y la respuesta.
En producción se reemplazaría con la integración real al OSE.
"""
import random
from apps.comprobantes.models import Comprobante, LogEnvioSUNAT


def enviar_a_ose(comprobante):
    """Simula envío al OSE. 90% aceptación, 10% rechazo."""
    from apps.comprobantes.services import transicionar_estado

    transicionar_estado(comprobante, Comprobante.EstadoComprobante.ENVIADO)

    aceptado = random.random() < 0.9

    if aceptado:
        log = LogEnvioSUNAT.objects.create(
            comprobante=comprobante,
            estado_respuesta=LogEnvioSUNAT.EstadoRespuesta.ACEPTADO,
            codigo_respuesta='0',
            descripcion='La factura electrónica fue aceptada por SUNAT.'
        )
        transicionar_estado(comprobante, Comprobante.EstadoComprobante.ACEPTADO)
    else:
        log = LogEnvioSUNAT.objects.create(
            comprobante=comprobante,
            estado_respuesta=LogEnvioSUNAT.EstadoRespuesta.RECHAZADO,
            codigo_respuesta='2800',
            descripcion='Error en la estructura del comprobante (simulación).'
        )
        transicionar_estado(comprobante, Comprobante.EstadoComprobante.RECHAZADO)

    return log


def reenviar_comprobante(comprobante):
    """Reenvía un comprobante RECHAZADO al OSE."""
    if comprobante.estado != Comprobante.EstadoComprobante.RECHAZADO:
        from django.core.exceptions import ValidationError
        raise ValidationError('Solo se pueden reenviar comprobantes RECHAZADOS.')
    return enviar_a_ose(comprobante)
