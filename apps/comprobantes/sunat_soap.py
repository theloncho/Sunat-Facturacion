import base64
import zipfile
import io
import os
import logging
from lxml import etree
from zeep import Client
from zeep.wsse.username import UsernameToken
from zeep.transports import Transport
import requests
from django.conf import settings
from decouple import config

from zeep.plugins import HistoryPlugin

logger = logging.getLogger(__name__)

class SunatSoapClient:
    """
    Cliente SOAP para los servicios web de SUNAT (OSE/PSE).
    Conecta al ambiente Beta o Producción según configuración.
    """
    
    WSDL_LOCAL = os.path.join(os.path.dirname(__file__), "sunat_billService.wsdl")
    ENDPOINT_BETA = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"
    ENDPOINT_PROD = "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService"

    def __init__(self):
        self.username = f"{config('SUNAT_RUC')}{config('SUNAT_USER')}"
        self.password = config('SUNAT_PASSWORD')
        self.is_beta = config('SUNAT_BETA_MODE', default=True, cast=bool)
        
        endpoint = self.ENDPOINT_BETA if self.is_beta else self.ENDPOINT_PROD
        
        self.history = HistoryPlugin()
        # Configurar cliente con el WSDL local para evitar errores de red/autenticación
        self.client = Client(
            wsdl=self.WSDL_LOCAL,
            wsse=UsernameToken(self.username, self.password),
            plugins=[self.history]
        )
        
        # Sobreescribir el endpoint dinámicamente según el ambiente
        if self.is_beta:
             self.client.service._binding_options['address'] = self.ENDPOINT_BETA
        else:
             self.client.service._binding_options['address'] = self.ENDPOINT_PROD

    def _create_zip(self, file_name, content):
        """Crea un archivo ZIP en memoria con el contenido XML en UTF-8."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            # Forzamos codificación binaria UTF-8
            if isinstance(content, str):
                content = content.encode('utf-8')
            zip_file.writestr(file_name, content)
        return zip_buffer.getvalue()

    def send_bill(self, comprobante_obj, xml_content):
        """
        Envía un comprobante (Factura, Boleta, NC) a SUNAT.
        """
        file_name = f"{comprobante_obj.empresa.ruc}-{comprobante_obj.tipo_sunat}-{comprobante_obj.serie_numero}"
        xml_file_name = f"{file_name}.xml"
        zip_file_name = f"{file_name}.zip"

        # Crear ZIP
        zip_data = self._create_zip(xml_file_name, xml_content)
        zip_b64 = base64.b64encode(zip_data).decode('utf-8')

        try:
            # Llamar al servicio sendBill
            # Retorna el CDR (Constancia de Recepción) en un ZIP base64
            response = self.client.service.sendBill(
                fileName=zip_file_name,
                contentFile=zip_b64
            )
            
            # Decodificar el CDR
            cdr_zip = base64.b64decode(response)
            return self._process_cdr(cdr_zip, file_name)
            
        except Exception as e:
            if hasattr(self, 'history'):
                if self.history.last_sent:
                    logger.error("SOAP REQUEST ENVELOPE:\n%s", etree.tostring(self.history.last_sent['envelope'], pretty_print=True).decode('utf-8'))
                if self.history.last_received:
                    logger.error("SOAP RESPONSE ENVELOPE:\n%s", etree.tostring(self.history.last_received['envelope'], pretty_print=True).decode('utf-8'))
            return {
                'success': False,
                'error': str(e),
                'code': 'ERROR_CONEXION'
            }

    def _process_cdr(self, cdr_zip_data, file_prefix):
        """
        Procesa el ZIP del CDR devuelto por SUNAT.
        Extrae el código y descripción de respuesta.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(cdr_zip_data)) as z:
                # El archivo dentro suele llamarse R-20000000001-01-F001-1.xml
                cdr_name = f"R-{file_prefix}.xml"
                if cdr_name not in z.namelist():
                    # Buscar cualquier XML si el nombre no coincide exacto
                    xml_files = [f for f in z.namelist() if f.endswith('.xml')]
                    cdr_name = xml_files[0] if xml_files else None
                
                if not cdr_name:
                    return {'success': False, 'error': 'No se encontró XML en el CDR'}

                with z.open(cdr_name) as f:
                    xml_tree = etree.fromstring(f.read())
                    
                # Namespaces comunes en el CDR
                ns = {
                    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                    'ar': 'urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2'
                }
                
                # Extraer código y descripción (ResponseCode y Description)
                code = xml_tree.xpath('//cbc:ResponseCode/text()', namespaces=ns)
                desc = xml_tree.xpath('//cbc:Description/text()', namespaces=ns)
                
                response_code = code[0] if code else '?'
                response_desc = desc[0] if desc else 'Sin descripción'

                return {
                    'success': response_code == '0',
                    'code': response_code,
                    'description': response_desc,
                    'cdr_xml': etree.tostring(xml_tree, encoding='unicode'),
                    'cdr_zip_b64': base64.b64encode(cdr_zip_data).decode('utf-8')
                }
        except Exception as e:
            return {'success': False, 'error': f"Error procesando CDR: {str(e)}"}
