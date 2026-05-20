import os
import io
import base64
import hashlib
import copy
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

# Algoritmos XMLDSig
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
ENVELOPED_SIG_ALG = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
RSA_SHA256_ALG = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256_ALG = "http://www.w3.org/2001/04/xmlenc#sha256"


def _c14n_of_element(element):
    """Retorna la forma canónica C14N de un elemento como bytes."""
    buf = io.BytesIO()
    etree.ElementTree(element).write_c14n(buf, exclusive=False, with_comments=False)
    return buf.getvalue()


def _c14n_of_tree_excluding(root, exclude_element):
    """
    Retorna la C14N del árbol completo EXCLUYENDO el elemento indicado.
    Simula la transformación enveloped-signature (URI="" + enveloped transform).
    """
    root_copy = copy.deepcopy(root)
    ns = {'ds': DS}
    sig_nodes = root_copy.xpath('//ds:Signature', namespaces=ns)
    for sig in sig_nodes:
        parent = sig.getparent()
        if parent is not None:
            parent.remove(sig)
    buf = io.BytesIO()
    etree.ElementTree(root_copy).write_c14n(buf, exclusive=False, with_comments=False)
    return buf.getvalue()


class SunatSigner:
    """
    Firma documentos XML UBL 2.1 con XMLDSig enveloped signature.
    Implementación directa con cryptography.
    """

    def __init__(self, pfx_path, pfx_password):
        self.pfx_path = pfx_path
        self.pfx_password = pfx_password
        self._load_certificate()

    def _load_certificate(self):
        if not os.path.exists(self.pfx_path):
            raise FileNotFoundError(f"No se encontró el certificado en {self.pfx_path}")
        with open(self.pfx_path, "rb") as f:
            pfx_data = f.read()
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            pfx_data, self.pfx_password.encode()
        )
        self.key = private_key
        self.cert = certificate

    def sign_xml(self, xml_string):
        parser = etree.XMLParser(remove_blank_text=False)
        if xml_string.startswith('<?xml'):
            xml_string = xml_string[xml_string.find('?>')+2:].strip()

        root = etree.fromstring(xml_string.encode('utf-8'), parser)

        nsmap_ds = {'ds': DS}
        ns = {
            'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
            'ds': DS
        }

        # ── PASO 1: Construir estructura ds:Signature vacía ────────────────
        signature_node = etree.Element(f'{{{DS}}}Signature', nsmap=nsmap_ds)
        signature_node.set('Id', 'SignatureSP')

        signed_info = etree.SubElement(signature_node, f'{{{DS}}}SignedInfo')

        canon_method = etree.SubElement(signed_info, f'{{{DS}}}CanonicalizationMethod')
        canon_method.set('Algorithm', C14N_ALG)

        sig_method = etree.SubElement(signed_info, f'{{{DS}}}SignatureMethod')
        sig_method.set('Algorithm', RSA_SHA256_ALG)

        reference = etree.SubElement(signed_info, f'{{{DS}}}Reference')
        reference.set('URI', '')

        transforms = etree.SubElement(reference, f'{{{DS}}}Transforms')

        transform_env = etree.SubElement(transforms, f'{{{DS}}}Transform')
        transform_env.set('Algorithm', ENVELOPED_SIG_ALG)

        transform_c14n = etree.SubElement(transforms, f'{{{DS}}}Transform')
        transform_c14n.set('Algorithm', C14N_ALG)

        digest_method_elem = etree.SubElement(reference, f'{{{DS}}}DigestMethod')
        digest_method_elem.set('Algorithm', SHA256_ALG)

        digest_value_elem = etree.SubElement(reference, f'{{{DS}}}DigestValue')
        digest_value_elem.text = ''

        sig_value_elem = etree.SubElement(signature_node, f'{{{DS}}}SignatureValue')
        sig_value_elem.text = ''

        key_info = etree.SubElement(signature_node, f'{{{DS}}}KeyInfo')
        x509_data = etree.SubElement(key_info, f'{{{DS}}}X509Data')
        x509_cert_elem = etree.SubElement(x509_data, f'{{{DS}}}X509Certificate')
        cert_der = self.cert.public_bytes(Encoding.DER)
        x509_cert_elem.text = base64.b64encode(cert_der).decode('ascii')

        # ── PASO 2: Insertar Signature en ExtensionContent ─────────────────
        ext_content = root.xpath(
            '//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent',
            namespaces=ns
        )
        if not ext_content:
            raise ValueError("No se encontró ExtensionContent en el XML.")
        ext_content[0].append(signature_node)

        # ── PASO 3: Calcular DigestValue ───────────────────────────────────
        doc_c14n = _c14n_of_tree_excluding(root, signature_node)
        digest_bytes = hashlib.sha256(doc_c14n).digest()
        digest_value_elem.text = base64.b64encode(digest_bytes).decode('ascii')

        # ── PASO 4: Calcular SignatureValue ────────────────────────────────
        signed_info_c14n = _c14n_of_element(signed_info)

        signature_bytes = self.key.sign(
            signed_info_c14n,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        sig_value_elem.text = base64.b64encode(signature_bytes).decode('ascii')

        # ── PASO 5: Serializar ─────────────────────────────────────────────
        xml_bytes = etree.tostring(root, xml_declaration=False, encoding='UTF-8')
        return '<?xml version="1.0" encoding="utf-8"?>\n' + xml_bytes.decode('utf-8')

    def get_hash(self, xml_string):
        if xml_string.startswith('<?xml'):
            xml_string = xml_string[xml_string.find('?>')+2:].strip()
        root = etree.fromstring(xml_string.encode('utf-8'))
        ns = {'ds': DS}
        digest = root.xpath('//ds:DigestValue/text()', namespaces=ns)
        return digest[0] if digest else ""
