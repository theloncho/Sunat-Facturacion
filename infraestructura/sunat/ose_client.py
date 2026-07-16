"""
SUNAT OSE Client - Para entorno BETA/DESARROLLO
Usa zeep con WSDL local para máxima compatibilidad y seguridad.
"""

import logging
import os
import base64
from django.conf import settings
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.wsse.username import UsernameToken
import requests
from decouple import config

logger = logging.getLogger(__name__)


class OSEClient:
    """
    Cliente SOAP para comunicación con SUNAT/OSE usando zeep con WSDL local.

    Usa un archivo WSDL local (wsdl/billService.wsdl) para evitar dependencia
    de red en la inicialización y resolver problemas de autenticación en el handshake.

    Importante: El WSDL usa <wsdl:import location="billService_ns1.wsdl"/> con
    ruta relativa. Zeep necesita un URI file:/// (no un path Windows directo)
    para resolver ese import correctamente.
    """

    def __init__(self, wsdl_path=None, ruc=None, usuario=None, password=None, service_url=None):
        """
        Inicializa el cliente SOAP con credenciales SOL y WSDL local.

        Args:
            wsdl_path: Path al archivo WSDL local. Si None, usa WSDL local por defecto.
            ruc: RUC de la empresa (11 dígitos).
            usuario: Usuario SOL (solo el sufijo, ej: JAVISIS1).
            password: Contraseña SOL.
            service_url: URL del servicio SOAP (endpoint). Si None, usa la del WSDL local.
        Raises:
            RuntimeError: Si Zeep no puede cargar el WSDL, con el error real detallado.
        """
        self.ruc = ruc or os.getenv('SUNAT_OSE_RUC', '')
        self.usuario = usuario or os.getenv('SUNAT_OSE_USUARIO', '')
        self.password = password or os.getenv('SUNAT_OSE_PASSWORD', '')
        self.service_url = service_url or os.getenv('SUNAT_OSE_WSDL', '')

        # SUNAT requiere credenciales en formato RUC-USUARIO
        username = f"{self.ruc}-{self.usuario}"
        wsse = UsernameToken(username, self.password)

        import pathlib

        # SIEMPRE usar WSDL local para evitar dependencia de red
        if not wsdl_path:
            wsdl_path = os.path.join(os.path.dirname(__file__), 'wsdl', 'billService.wsdl')

        # Convertir path Windows a URI file:/// para que Zeep resuelva
        # correctamente los imports relativos del WSDL (billService_ns1.wsdl)
        wsdl_uri = pathlib.Path(wsdl_path).as_uri()
        self.wsdl_path = wsdl_uri

        logger.info(f"Cargando WSDL local: {wsdl_path}")
        if self.service_url:
            logger.info(f"Endpoint SOAP: {self.service_url}")

        transport = Transport(timeout=60)
        zeep_settings = Settings(strict=False, xml_huge_tree=True)

        try:
            self.client = Client(
                wsdl=wsdl_uri,
                wsse=wsse,
                transport=transport,
                settings=zeep_settings
            )
            logger.info(f"Cliente OSE inicializado. Servicios: {list(self.client.wsdl.services.keys())}")

            # Override del endpoint si se proporciono una URL de servicio
            if self.service_url:
                service = self.client.service
                service._binding_options['address'] = self.service_url
                logger.info(f"Endpoint sobrescrito a: {self.service_url}")
        except Exception as e:
            msg = (
                f"Error inicializando cliente Zeep con WSDL '{wsdl_uri}': {e}\n"
                f"  RUC: {self.ruc} | Usuario: {self.ruc}-{self.usuario}\n"
                f"  Verifique que el archivo WSDL exista y sea valido."
            )
            logger.error(msg)
            raise RuntimeError(msg) from e

    def send_bill(self, zip_content, file_name):
        """
        Envía un comprobante individual al OSE via SOAP sendBill.

        Args:
            zip_content (bytes | str): Contenido del ZIP (bytes o base64 string).
            file_name (str): Nombre del archivo ZIP con formato SUNAT:
                             RUC-TIPO-SERIE-NUMERO.zip (ej: 20103129061-01-F001-00000001.zip)
        Returns:
            dict: {status, applicationResponse, faultcode, faultstring}
                  status=0 indica éxito. applicationResponse contiene el CDR base64.
        """
        logger.info(f"Enviando comprobante: {file_name}")

        try:
            zip_bytes = base64.b64decode(zip_content) if isinstance(zip_content, str) else zip_content

            response = self.client.service.sendBill(
                fileName=file_name,
                contentFile=zip_bytes
            )

            return {
                'status': 0,
                'applicationResponse': base64.b64encode(response).decode('utf-8') if response else None,
                'faultcode': None,
                'faultstring': None
            }

        except Exception as e:
            logger.error(f"Error enviando a OSE: {str(e)}")
            return {
                'status': -1,
                'ticket': None,
                'faultcode': getattr(e, 'code', 'ERROR'),
                'faultstring': getattr(e, 'message', str(e))
            }

    def get_status(self, ticket):
        """
        Consulta el estado de un ticket asíncrono (lotes sendPack).

        Args:
            ticket (str): Ticket devuelto por sendPack.
        Returns:
            dict: {status, ticket, faultcode, faultstring}
        """
        try:
            response = self.client.service.getStatus(ticket=ticket)
            return {
                'status': response.statusCode if hasattr(response, 'statusCode') else 0,
                'ticket': ticket,
                'faultcode': None,
                'faultstring': None
            }
        except Exception as e:
            logger.error(f"Error consultando ticket: {str(e)}")
            return {
                'status': -1,
                'ticket': ticket,
                'faultcode': getattr(e, 'code', 'ERROR'),
                'faultstring': getattr(e, 'message', str(e))
            }

    def get_status_cdr(self, ticket):
        """
        Obtiene el CDR (Constancia de Recepción) de un ticket aceptado.

        Args:
            ticket (str): Ticket previamente consultado con getStatus.
        Returns:
            dict: {status, cdrContent, faultcode, faultstring}
        """
        try:
            response = self.client.service.getStatusCdr(ticket=ticket)
            return {
                'status': 0,
                'cdrContent': response.content if hasattr(response, 'content') else None,
                'faultcode': None,
                'faultstring': None
            }
        except Exception as e:
            logger.error(f"Error consultando CDR: {str(e)}")
            return {
                'status': -1,
                'ticket': ticket,
                'faultcode': getattr(e, 'code', 'ERROR'),
                'faultstring': getattr(e, 'message', str(e))
            }

    def send_pack(self, zip_content, file_name):
        """
        Envía un lote de comprobantes al OSE via SOAP sendPack.

        A diferencia de sendBill, sendPack es asíncrono: retorna un ticket
        que debe consultarse posteriormente con getStatus().

        Args:
            zip_content (bytes | str): ZIP con múltiples XML firmados.
            file_name (str): Nombre del ZIP de lote.
        Returns:
            dict: {status, ticket, faultcode, faultstring}
        """
        try:
            zip_bytes = base64.b64decode(zip_content) if isinstance(zip_content, str) else zip_content

            response = self.client.service.sendPack(
                fileName=file_name,
                contentFile=zip_bytes
            )
            return {
                'status': 0,
                'ticket': response if isinstance(response, str) else None,
                'faultcode': None,
                'faultstring': None
            }
        except Exception as e:
            logger.error(f"Error enviando lote: {str(e)}")
            return {
                'status': -1,
                'ticket': None,
                'faultcode': getattr(e, 'code', 'ERROR'),
                'faultstring': getattr(e, 'message', str(e))
            }



class MockOSEClient:
    """
    Cliente MOCK para desarrollo local - SIMULA respuestas de SUNAT/OSE.
    
    ADVERTENCIA: Este cliente NO envia nada a SUNAT. Solo simula respuestas.
    Para conexion real, establecer SUNAT_OSE_MOCK=False en .env o docker-compose.yml
    """

    def __init__(self, *args, **kwargs):
        logger.warning("=" * 60)
        logger.warning("MOCK OSE CLIENT INICIALIZADO - NO SE ENVIA A SUNAT REAL")
        logger.warning("Para conexion real: SUNAT_OSE_MOCK=False")
        logger.warning("=" * 60)

    def send_bill(self, zip_content, file_name):
        import random
        import uuid
        import time

        logger.info(f"[MOCK] Simulando envio de {file_name} a SUNAT...")
        time.sleep(random.uniform(0.5, 1.5))

        if random.random() < 0.9:
            ticket = f"MOCK-{uuid.uuid4().hex[:10].upper()}"
            logger.info(f"[MOCK] Comprobante SIMULADO ACEPTADO - Ticket: {ticket}")
            logger.warning(f"[MOCK] ESTO ES UNA SIMULACION - NO SE ENVIO A SUNAT")
            return {
                'status': 0,
                'ticket': ticket,
                'applicationResponse': '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',
                'faultcode': None,
                'faultstring': None
            }
        else:
            return {
                'status': 99,
                'ticket': None,
                'faultcode': '2000',
                'faultstring': random.choice([
                    "Error de negocio: Numeración duplicada",
                    "Error de estructura: Formato inválido de XML",
                    "Error de datos: RUC no existe en padrón",
                    "Error de validación: Fecha fuera de rango",
                ])
            }

    def get_status(self, ticket):
        import random
        import time

        logger.info(f"[MOCK] Consultando estado del ticket: {ticket}")
        time.sleep(random.uniform(0.3, 1.0))

        return {
            'status': 0,
            'ticket': ticket,
            'faultcode': None,
            'faultstring': None
        }

    def get_status_cdr(self, ticket):
        import random
        import time
        import base64

        logger.info(f"[MOCK] Obteniendo CDR del ticket: {ticket}")
        time.sleep(random.uniform(0.3, 1.0))

        # Retornar un ZIP mock real codificado en base64 y decodificado a bytes
        mock_cdr_b64 = 'UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=='
        mock_cdr = base64.b64decode(mock_cdr_b64)

        return {
            'status': 0,
            'cdrContent': mock_cdr,
            'faultcode': None,
            'faultstring': None
        }

    def send_pack(self, zip_content, file_name):
        import random
        import uuid
        import time

        logger.info(f"[MOCK] Simulando envio de lote: {file_name}")
        time.sleep(random.uniform(1.0, 2.0))

        if random.random() < 0.9:
            return {
                'status': 0,
                'ticket': f"LOTE-{uuid.uuid4().hex[:10].upper()}",
                'faultcode': None,
                'faultstring': None
            }
        else:
            return {
                'status': 99,
                'ticket': None,
                'faultcode': '3000',
                'faultstring': random.choice([
                    "Error de lote: Archivos duplicados",
                    "Error de lote: Fecha de emisión不一致",
                    "Error de lote: Estructura ZIP inválida",
                ])
            }


def get_ose_client(use_mock=None):
    """Factory function para obtener el cliente OSE apropiado."""
    if use_mock is None:
        # Si SUNAT_BETA_MODE es True, queremos NO usar mock (es decir, mock = False)
        beta_mode = config('SUNAT_BETA_MODE', default=False, cast=bool)
        use_mock = not beta_mode

    if use_mock:
        logger.warning("get_ose_client: Usando MockOSEClient (SIMULACION - NO envia a SUNAT)")
        return MockOSEClient()
    else:
        ruc = os.getenv('SUNAT_RUC', os.getenv('SUNAT_OSE_RUC', ''))
        usuario = os.getenv('SUNAT_USER', os.getenv('SUNAT_OSE_USUARIO', ''))
        password = os.getenv('SUNAT_PASSWORD', os.getenv('SUNAT_OSE_PASSWORD', ''))
        service_url = os.getenv('SUNAT_OSE_WSDL', '')
        
        logger.info(f"get_ose_client: Usando OSEClient (conexion REAL a SUNAT) para RUC {ruc}")
        return OSEClient(ruc=ruc, usuario=usuario, password=password, service_url=service_url) if ruc else None