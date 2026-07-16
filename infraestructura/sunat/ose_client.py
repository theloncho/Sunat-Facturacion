"""
SUNAT OSE Client - Para entorno BETA/DESARROLLO
Usa requests puro para máxima compatibilidad y ligereza (sin dependencias pesadas como zeep).
"""

import logging
import os
import base64
import requests
import xml.etree.ElementTree as ET
from decouple import config

logger = logging.getLogger(__name__)

class OSEClient:
    """
    Cliente SOAP para comunicación con SUNAT/OSE usando HTTP requests puro.
    
    Implementa el protocolo SOAP y WS-Security de forma manual, evitando librerías
    obsoletas o conflictivas.
    """

    def __init__(self, wsdl_path=None, ruc=None, usuario=None, password=None, service_url=None):
        self.ruc = ruc or os.getenv('SUNAT_OSE_RUC', '')
        self.usuario = usuario or os.getenv('SUNAT_OSE_USUARIO', '')
        self.password = password or os.getenv('SUNAT_OSE_PASSWORD', '')
        # Endpoint por defecto de SUNAT Beta
        self.service_url = service_url or os.getenv('SUNAT_OSE_WSDL', 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService')
        
        # SUNAT requiere credenciales en formato RUC-USUARIO para WS-Security
        self.username = f"{self.ruc}-{self.usuario}"

        logger.info(f"Cliente OSE (Requests HTTP) inicializado para RUC: {self.ruc}")
        logger.info(f"Endpoint SOAP: {self.service_url}")

    def send_bill(self, zip_content, file_name):
        """
        Envía un comprobante individual al OSE via SOAP HTTP POST.
        """
        logger.info(f"Enviando comprobante HTTP: {file_name}")

        try:
            zip_b64 = zip_content if isinstance(zip_content, str) else base64.b64encode(zip_content).decode('utf-8')
            
            # Construir el envelope SOAP puro con WS-Security y sendBill
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<soapenv:Header>
    <wsse:Security>
        <wsse:UsernameToken>
            <wsse:Username>{self.username}</wsse:Username>
            <wsse:Password>{self.password}</wsse:Password>
        </wsse:UsernameToken>
    </wsse:Security>
</soapenv:Header>
<soapenv:Body>
    <ser:sendBill>
        <fileName>{file_name}</fileName>
        <contentFile>{zip_b64}</contentFile>
    </ser:sendBill>
</soapenv:Body>
</soapenv:Envelope>"""

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'urn:sendBill'
            }

            response = requests.post(self.service_url, data=soap_envelope.encode('utf-8'), headers=headers, timeout=60)
            
            if response.status_code == 200:
                # Extraer applicationResponse (el CDR en ZIP)
                root = ET.fromstring(response.text)
                # Buscar el tag applicationResponse ignorando namespace para más robustez
                app_resp = None
                for elem in root.iter():
                    if elem.tag.endswith('}applicationResponse') or elem.tag == 'applicationResponse':
                        app_resp = elem
                        break
                
                cdr_b64 = app_resp.text if app_resp is not None else None
                
                return {
                    'status': 0,
                    'applicationResponse': cdr_b64,
                    'faultcode': None,
                    'faultstring': None
                }
            else:
                logger.error(f"Error HTTP SUNAT: {response.status_code} - {response.text}")
                
                # Intentar extraer el faultcode y faultstring
                faultcode = str(response.status_code)
                faultstring = "Error en conexión con SUNAT"
                try:
                    root = ET.fromstring(response.text)
                    for elem in root.iter():
                        if elem.tag.endswith('}faultcode') or elem.tag == 'faultcode':
                            if elem.text: faultcode = elem.text
                        elif elem.tag.endswith('}faultstring') or elem.tag == 'faultstring':
                            if elem.text: faultstring = elem.text
                except:
                    pass

                return {
                    'status': -1,
                    'ticket': None,
                    'faultcode': faultcode,
                    'faultstring': faultstring
                }

        except Exception as e:
            logger.error(f"Error enviando a OSE HTTP: {str(e)}")
            return {
                'status': -1,
                'ticket': None,
                'faultcode': 'ERROR_HTTP',
                'faultstring': str(e)
            }
            
    def get_status(self, ticket):
        return {'status': -1, 'ticket': ticket, 'faultcode': 'NO_IMPL', 'faultstring': 'Método no implementado en cliente ligero'}
        
    def get_status_cdr(self, ticket):
        return {'status': -1, 'ticket': ticket, 'faultcode': 'NO_IMPL', 'faultstring': 'Método no implementado en cliente ligero'}
        
    def send_pack(self, zip_content, file_name):
        return {'status': -1, 'ticket': None, 'faultcode': 'NO_IMPL', 'faultstring': 'Método no implementado en cliente ligero'}



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