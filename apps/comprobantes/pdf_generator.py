"""
Generador de PDF para comprobantes electrónicos en formato voucher.
Usa ReportLab para crear PDFs con formato profesional.
"""
from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def generar_pdf_comprobante(comprobante):
    """Genera un PDF con formato voucher para el comprobante."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=14, spaceAfter=6)
    subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)
    normal = styles['Normal']
    bold_style = ParagraphStyle('Bold', parent=normal, fontName='Helvetica-Bold')

    elements = []

    # ── Encabezado empresa ────────────────────────────────────────
    elements.append(Paragraph(comprobante.empresa.razon_social, title_style))
    elements.append(Paragraph(f"RUC: {comprobante.empresa.ruc}", subtitle_style))
    elements.append(Paragraph(comprobante.empresa.direccion, subtitle_style))
    elements.append(Spacer(1, 10*mm))

    # ── Tipo y número ─────────────────────────────────────────────
    tipo_display = comprobante.get_tipo_display()
    elements.append(Paragraph(f"{tipo_display} ELECTRÓNICA", ParagraphStyle(
        'TipoComp', parent=styles['Heading2'], alignment=TA_CENTER,
        textColor=colors.HexColor('#1a237e'), fontSize=16
    )))
    elements.append(Paragraph(comprobante.serie_numero, ParagraphStyle(
        'SerieNum', parent=styles['Heading3'], alignment=TA_CENTER, fontSize=14
    )))
    elements.append(Paragraph(f"Fecha: {comprobante.fecha_emision}", subtitle_style))
    elements.append(Spacer(1, 8*mm))

    # ── Datos del cliente ─────────────────────────────────────────
    client_data = [
        ['Cliente:', comprobante.cliente.razon_social],
        [f'{comprobante.cliente.tipo_doc}:', comprobante.cliente.num_doc],
        ['Dirección:', comprobante.cliente.direccion or 'N/A'],
    ]
    client_table = Table(client_data, colWidths=[80, 400])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 8*mm))

    # ── Tabla de detalles ─────────────────────────────────────────
    header = ['#', 'Descripción', 'Cant.', 'P. Unit.', 'Desc.%', 'IGV', 'Subtotal']
    detail_data = [header]

    for idx, d in enumerate(comprobante.detalles.select_related('producto').all(), 1):
        detail_data.append([
            str(idx),
            d.producto.descripcion[:40],
            f"{d.cantidad:.2f}",
            f"S/.{d.precio_unitario:.2f}",
            f"{d.descuento:.1f}%",
            f"S/.{d.igv_linea:.2f}",
            f"S/.{d.subtotal:.2f}",
        ])

    detail_table = Table(detail_data, colWidths=[25, 180, 45, 65, 45, 55, 65])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 6*mm))

    # ── Totales ───────────────────────────────────────────────────
    totals_data = [
        ['Base Imponible:', f'S/.{comprobante.subtotal:.2f}'],
        ['IGV (18%):', f'S/.{comprobante.igv:.2f}'],
        ['TOTAL:', f'S/.{comprobante.total:.2f}'],
    ]
    if comprobante.total_inafecto > 0:
        totals_data.insert(1, ['Total Inafecto:', f'S/.{comprobante.total_inafecto:.2f}'])

    totals_table = Table(totals_data, colWidths=[380, 100])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 10*mm))

    # ── Estado SUNAT ──────────────────────────────────────────────
    estado_color = {
        'ACEPTADO': '#4caf50', 'RECHAZADO': '#f44336',
        'ENVIADO': '#ff9800', 'EMITIDO': '#2196f3', 'BORRADOR': '#9e9e9e',
    }
    color = estado_color.get(comprobante.estado, '#9e9e9e')
    elements.append(Paragraph(
        f'Estado SUNAT: <b>{comprobante.get_estado_display()}</b>',
        ParagraphStyle('Estado', parent=normal, alignment=TA_CENTER,
                       textColor=colors.HexColor(color), fontSize=12)
    ))

    if comprobante.hash_cpe:
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph(
            f'Hash: {comprobante.hash_cpe[:20]}...',
            ParagraphStyle('Hash', parent=normal, alignment=TA_CENTER,
                           fontSize=7, textColor=colors.grey)
        ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
