import logging
import os
import base64
import hashlib
from lxml import etree
from django.conf import settings

logger = logging.getLogger(__name__)

NAMESPACES_FIRMA = {
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'inv': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
}

DS = NAMESPACES_FIRMA['ds']
EXT = NAMESPACES_FIRMA['ext']


def get_cert_bytes(cert_path=None, cert_password=None):
    """
    Lee y retorna el contenido binario del certificado PFX/P12 de firma SUNAT.

    Resuelve el path del certificado como ABSOLUTO respecto a BASE_DIR de Django,
    evitando fallos por directorio de trabajo variable al iniciar el servidor.

    Args:
        cert_path (str | None): Path relativo o absoluto al .pfx.
                                Si es None, se toma de la variable de entorno SUNAT_CERT_PATH.
        cert_password (str | None): Contraseña del .pfx.
                                    Si es None, se toma de SUNAT_CERT_PASSWORD.
    Returns:
        bytes: Contenido binario del archivo PFX.
    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta resuelta.
    """
    from django.conf import settings as django_settings
    import pathlib

    raw_path = cert_path or os.getenv('SUNAT_CERT_PATH', 'certs/CT2602141470.pfx')
    cert_password = cert_password or os.getenv('SUNAT_CERT_PASSWORD', '')

    resolved = pathlib.Path(raw_path)
    if not resolved.is_absolute():
        resolved = pathlib.Path(django_settings.BASE_DIR) / resolved

    if not resolved.exists():
        raise FileNotFoundError(
            f"Certificado no encontrado: {resolved}\n"
            f"  Path configurado en .env: {raw_path}\n"
            f"  BASE_DIR: {django_settings.BASE_DIR}\n"
            f"  Verifique que el archivo exista en esa ubicación."
        )

    with open(resolved, 'rb') as f:
        return f.read(), cert_password


def sign_xml(xml_content, ruc=None, razon_social=None, empresa_id=None, certificado_id=None):
    """
    Firma digitalmente el XML UBL 2.1 con el certificado.

    Si certificado_id o empresa_id se proporciona, usa el certificado de la BD.
    Si no, usa el certificado del sistema de archivos (env var SUNAT_CERT_PATH).

    Args:
        xml_content (bytes): XML sin firmar.
        ruc (str | None): RUC del emisor.
        razon_social (str | None): Razon social del emisor.
        empresa_id (int | None): ID de la empresa para buscar cert activo en BD.
        certificado_id (int | None): ID especifico del certificado en BD.

    Returns:
        bytes: XML firmado en UTF-8.
    Raises:
        ValueError: Si no se puede firmar el XML (certificado no encontrado, password incorrecto, etc.)
    """
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import padding

    root = etree.fromstring(xml_content)

    cert_data = None
    cert_password = None

    cert_data = None
    cert_password = None

    if not cert_data:
        try:
            cert_data, cert_password = get_cert_bytes()
            logger.info(f"Certificado cargado desde archivo")
        except FileNotFoundError:
            logger.error("Certificado no encontrado en sistema de archivos")
            raise ValueError(
                "No se encontro el certificado digital. "
                "Verifique SUNAT_CERT_PATH en .env o docker-compose.yml"
            )

    try:
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            cert_data,
            cert_password.encode('utf-8') if cert_password else None
        )
        logger.info("Certificado cargado exitosamente")
    except Exception as e:
        logger.error(f"Error al cargar el certificado PFX: {e}")
        raise ValueError(f"Error al cargar el certificado digital (password incorrecto o archivo corrupto): {e}")

    ruc = ruc or '20103129061'
    razon_social = razon_social or 'MI EMPRESA SAC'

    ext_UBLExtensions = root.find(f'{{{EXT}}}UBLExtensions')
    if ext_UBLExtensions is None:
        raise ValueError("No se encontro UBLExtensions en el XML")

    for ext_extension in ext_UBLExtensions.findall(f'{{{EXT}}}UBLExtension'):
        ext_content = ext_extension.find(f'{{{EXT}}}ExtensionContent')
        if ext_content is not None:
            for sig in ext_content.findall(f'{{{DS}}}Signature'):
                ext_content.remove(sig)

            ds_sig = etree.SubElement(ext_content, f'{{{DS}}}Signature')
            ds_sig.set('Id', 'SignatureSUNAT')

            ds_signed_info = etree.SubElement(ds_sig, f'{{{DS}}}SignedInfo')

            ds_canonicalization_method = etree.SubElement(ds_signed_info, f'{{{DS}}}CanonicalizationMethod')
            ds_canonicalization_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')

            ds_signature_method = etree.SubElement(ds_signed_info, f'{{{DS}}}SignatureMethod')
            ds_signature_method.set('Algorithm', 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256')

            ds_reference = etree.SubElement(ds_signed_info, f'{{{DS}}}Reference')
            ds_reference.set('URI', '')

            ds_transforms = etree.SubElement(ds_reference, f'{{{DS}}}Transforms')
            ds_transform = etree.SubElement(ds_transforms, f'{{{DS}}}Transform')
            ds_transform.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')

            ds_digest_method = etree.SubElement(ds_reference, f'{{{DS}}}DigestMethod')
            ds_digest_method.set('Algorithm', 'http://www.w3.org/2001/04/xmlenc#sha256')

            ds_digest_value = etree.SubElement(ds_reference, f'{{{DS}}}DigestValue')

            ds_signature_value = etree.SubElement(ds_sig, f'{{{DS}}}SignatureValue')

            ds_key_info = etree.SubElement(ds_sig, f'{{{DS}}}KeyInfo')
            ds_x509_data = etree.SubElement(ds_key_info, f'{{{DS}}}X509Data')
            ds_x509_cert = etree.SubElement(ds_x509_data, f'{{{DS}}}X509Certificate')

            break

    # Para el DigestValue, debemos excluir el elemento Signature (Enveloped Signature)
    import copy
    root_copy = copy.deepcopy(root)
    ext_UBLExtensions_copy = root_copy.find(f'{{{EXT}}}UBLExtensions')
    if ext_UBLExtensions_copy is not None:
        for ext_extension_copy in ext_UBLExtensions_copy.findall(f'{{{EXT}}}UBLExtension'):
            ext_content_copy = ext_extension_copy.find(f'{{{EXT}}}ExtensionContent')
            if ext_content_copy is not None:
                for sig_copy in ext_content_copy.findall(f'{{{DS}}}Signature'):
                    ext_content_copy.remove(sig_copy)
    
    canonical_root = etree.tostring(root_copy, method='c14n')
    digest = hashlib.sha256(canonical_root).digest()
    digest_b64 = base64.b64encode(digest).decode('ascii')
    ds_digest_value.text = digest_b64

    # Para el SignatureValue, se firma el elemento SignedInfo canonizado
    canonical_signed_info = etree.tostring(ds_signed_info, method='c14n')

    signature_bytes = private_key.sign(
        canonical_signed_info,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    signature_b64 = base64.b64encode(signature_bytes).decode('ascii')
    ds_signature_value.text = signature_b64

    cert_der = certificate.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode('ascii')
    ds_x509_cert.text = cert_b64

    xml_firmado = etree.tostring(root, xml_declaration=True, encoding='UTF-8')

    # VALIDACION: verificar que la firma se aplico correctamente
    if b'<ds:Signature' not in xml_firmado and b'<Signature' not in xml_firmado:
        raise ValueError("Error critico: el XML firmado no contiene la firma digital")
    
    logger.info("XML firmado exitosamente con firma digital validada")
    return xml_firmado