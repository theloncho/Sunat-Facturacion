import random
import base64
import logging
import io
import zipfile
from typing import Tuple
from decouple import config

from dominio.comprobantes.entidades import Comprobante
from dominio.comprobantes.puertos import ISunatClient, IComprobanteRepository
from dominio.comprobantes.excepciones import TransicionEstadoException
from apps.comprobantes.models import LogEnvioSUNAT
from .xml_generator import generar_xml_comprobante
from .ose_client import get_ose_client

logger = logging.getLogger(__name__)


class DjangoSunatClient(ISunatClient):
    """Adaptador de infraestructura para interactuar con la OSE/SUNAT."""

    def __init__(self, comp_repo: IComprobanteRepository):
        self.comp_repo = comp_repo

    def generar_xml(self, comprobante: Comprobante) -> Tuple[bytes, str]:
        return generar_xml_comprobante(comprobante)
        
    def enviar_comprobante(self, comprobante: Comprobante) -> None:
        if comprobante.estado not in ['EMITIDO', 'RECHAZADO']:
            raise TransicionEstadoException('Solo comprobantes EMITIDOS o RECHAZADOS pueden enviarse.')
            
        comprobante.estado = 'ENVIADO'
        self.comp_repo.actualizar_comprobante(comprobante, estado='ENVIADO')

        ose_client = get_ose_client(use_mock=not config('SUNAT_BETA_MODE', default=True, cast=bool) and config('SUNAT_OSE_MOCK', default=True, cast=bool))
        
        file_name = f"{comprobante.empresa.ruc}-{comprobante.tipo_sunat}-{comprobante.serie_numero}"
        xml_file_name = f"{file_name}.xml"
        zip_file_name = f"{file_name}.zip"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            xml_content = comprobante.xml_firmado
            if isinstance(xml_content, str):
                xml_content = xml_content.encode('utf-8')
            zip_file.writestr(xml_file_name, xml_content)
        
        zip_data = zip_buffer.getvalue()
        zip_base64 = base64.b64encode(zip_data).decode('utf-8')

        resultado = ose_client.send_bill(zip_base64, zip_file_name)
        
        if resultado.get('status') == 0:
            LogEnvioSUNAT.objects.create(
                comprobante_id=comprobante.id,
                estado_respuesta='ACEPTADO',
                codigo_respuesta='0',
                descripcion='CDR recibido - Comprobante aceptado por SUNAT/OSE'
            )
            comprobante.estado = 'ACEPTADO'
            
            # GUARDAR EL CDR FÍSICO PARA DEMOSTRAR QUE ES REAL
            cdr_base64 = resultado.get('applicationResponse')
            if cdr_base64:
                import os
                cdr_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'cdrs')
                os.makedirs(cdr_dir, exist_ok=True)
                cdr_path = os.path.join(cdr_dir, f"R-{zip_file_name}")
                with open(cdr_path, 'wb') as f:
                    f.write(base64.b64decode(cdr_base64))
                logger.info(f"CDR REAL GUARDADO EN: {cdr_path}")
        else:
            LogEnvioSUNAT.objects.create(
                comprobante_id=comprobante.id,
                estado_respuesta='RECHAZADO',
                codigo_respuesta=resultado.get('faultcode', 'ERR'),
                descripcion=resultado.get('faultstring', 'Error desconocido')
            )
            comprobante.estado = 'RECHAZADO'
        self.comp_repo.actualizar_comprobante(comprobante, estado=comprobante.estado)
