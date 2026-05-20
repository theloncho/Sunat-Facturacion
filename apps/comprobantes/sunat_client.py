"""
Mock OSE (Operador de Servicios Electrónicos) Client.
Simula el envío de comprobantes a SUNAT y la respuesta.
En producción se reemplazaría con la integración real al OSE.
"""
import random
from decouple import config
from apps.comprobantes.models import Comprobante, LogEnvioSUNAT
from apps.comprobantes.sunat_soap import SunatSoapClient


def enviar_a_ose(comprobante):
    """Simula envío al OSE. 90% aceptación, 10% rechazo."""
    from apps.comprobantes.services import transicionar_estado

    transicionar_estado(comprobante, Comprobante.EstadoComprobante.ENVIADO)

    # Verificamos si estamos en modo real (Beta o Prod)
    if config('SUNAT_BETA_MODE', default=True, cast=bool):
        soap_client = SunatSoapClient()
        resultado = soap_client.send_bill(comprobante, comprobante.xml_firmado)
        
        if resultado['success']:
            log = LogEnvioSUNAT.objects.create(
                comprobante=comprobante,
                estado_respuesta=LogEnvioSUNAT.EstadoRespuesta.ACEPTADO,
                codigo_respuesta=resultado['code'],
                descripcion=resultado['description']
            )
            transicionar_estado(comprobante, Comprobante.EstadoComprobante.ACEPTADO)
        else:
            estado_res = LogEnvioSUNAT.EstadoRespuesta.RECHAZADO
            if resultado.get('code') == 'ERROR_CONEXION':
                estado_res = LogEnvioSUNAT.EstadoRespuesta.EXCEPCION
                
            log = LogEnvioSUNAT.objects.create(
                comprobante=comprobante,
                estado_respuesta=estado_res,
                codigo_respuesta=resultado.get('code', 'ERR'),
                descripcion=resultado.get('error') or resultado.get('description')
            )
            transicionar_estado(comprobante, Comprobante.EstadoComprobante.RECHAZADO)
        return log

    # --- Lógica de Simulación (Mock) anterior ---
    aceptado = random.random() < 0.9
    if aceptado:
        log = LogEnvioSUNAT.objects.create(
            comprobante=comprobante,
            estado_respuesta=LogEnvioSUNAT.EstadoRespuesta.ACEPTADO,
            codigo_respuesta='0',
            descripcion='(Simulación) La factura electrónica fue aceptada por SUNAT.'
        )
        transicionar_estado(comprobante, Comprobante.EstadoComprobante.ACEPTADO)
    else:
        log = LogEnvioSUNAT.objects.create(
            comprobante=comprobante,
            estado_respuesta=LogEnvioSUNAT.EstadoRespuesta.RECHAZADO,
            codigo_respuesta='2800',
            descripcion='(Simulación) Error en la estructura del comprobante.'
        )
        transicionar_estado(comprobante, Comprobante.EstadoComprobante.RECHAZADO)

    return log


def reenviar_comprobante(comprobante):
    """Reenvía un comprobante RECHAZADO al OSE."""
    if comprobante.estado != Comprobante.EstadoComprobante.RECHAZADO:
        from django.core.exceptions import ValidationError
        raise ValidationError('Solo se pueden reenviar comprobantes RECHAZADOS.')
    return enviar_a_ose(comprobante)
