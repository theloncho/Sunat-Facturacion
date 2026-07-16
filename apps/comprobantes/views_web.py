"""Web views para comprobantes (Django Templates)."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json

from .models import Comprobante
from dominio.comprobantes.servicios import FacturaService, BoletaService, NotaCreditoService
from dominio.comprobantes.excepciones import ComprobanteException
from dominio.comprobantes.entidades import Cliente as DominioCliente, Empresa as DominioEmpresa
from infraestructura.persistencia.comprobante_repo import (
    DjangoComprobanteRepository, DjangoNumeracionRepository, DjangoProductoRepository
)
from infraestructura.sunat.cliente_ose import DjangoSunatClient
from infraestructura.sunat.firmar import get_certificate_info
from .pdf_generator import generar_pdf_comprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto


@login_required
def dashboard_view(request):
    """Dashboard principal con resumen del mes."""
    hoy = timezone.now()
    qs = Comprobante.objects.filter(empresa=request.user.empresa) if request.user.empresa else Comprobante.objects.none()
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
    mes_qs = qs.filter(fecha_emision__month=hoy.month, fecha_emision__year=hoy.year)

    stats = {
        'total_facturas': mes_qs.filter(tipo='FACTURA').count(),
        'total_boletas': mes_qs.filter(tipo='BOLETA').count(),
        'total_notas': mes_qs.filter(tipo='NOTA_CREDITO').count(),
        'monto_total': mes_qs.aggregate(t=Sum('total'))['t'] or Decimal('0.00'),
        'rechazados': mes_qs.filter(estado='RECHAZADO').count(),
        'aceptados': mes_qs.filter(estado='ACEPTADO').count(),
        'pendientes': mes_qs.filter(estado__in=['BORRADOR', 'EMITIDO', 'ENVIADO']).count(),
    }

    facturas = stats['total_facturas']
    boletas = stats['total_boletas']
    notas = stats['total_notas']
    total = facturas + boletas + notas
    if total > 0:
        pct_facturas = round(facturas / total * 100)
        pct_boletas = round(boletas / total * 100)
        pct_notas = 100 - pct_facturas - pct_boletas
    else:
        pct_facturas = pct_boletas = pct_notas = 0

    chart_total = total
    chart_data = {
        'labels': ['Facturas', 'Boletas', 'Notas de Crédito'],
        'data': [facturas, boletas, notas],
        'percentages': [pct_facturas, pct_boletas, pct_notas],
        'colors': ['#3b82f6', '#22c55e', '#f97316'],
    }

    rechazados_list = qs.filter(estado='RECHAZADO').order_by('-fecha_emision')[:5]
    
    cert_info = get_certificate_info()

    return render(request, 'dashboard/index.html', {
        'stats': stats,
        'rechazados_list': rechazados_list,
        'mes_actual': hoy.strftime('%B %Y'),
        'cert_info': cert_info,
        'chart_data': json.dumps(chart_data),
        'chart_total': chart_total,
    })


@csrf_exempt
@login_required
def emitir_comprobante_view(request):
    """Formulario para emitir factura o boleta."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'No tiene permisos para emitir comprobantes.'}, status=403)
        messages.error(request, 'No tiene permisos para acceder a esta página.')
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tipo = data.get('tipo', 'FACTURA')
            cliente_id = data.get('cliente_id')
            detalles = data.get('detalles', [])

            cliente_django = Cliente.objects.get(id=cliente_id)
            cliente_domain = DominioCliente(
                id=cliente_django.id, tipo_doc=cliente_django.tipo_doc,
                num_doc=cliente_django.num_doc, razon_social=cliente_django.razon_social,
                direccion=cliente_django.direccion, email=cliente_django.email
            )
            empresa_django = request.user.empresa
            empresa_domain = DominioEmpresa(
                id=empresa_django.id, ruc=empresa_django.ruc,
                razon_social=empresa_django.razon_social, nombre_comercial=empresa_django.nombre_comercial,
                direccion=empresa_django.direccion, regimen_tributario=empresa_django.regimen_tributario
            )
            
            comp_repo = DjangoComprobanteRepository()
            num_repo = DjangoNumeracionRepository()
            prod_repo = DjangoProductoRepository()
            sunat_client = DjangoSunatClient(comp_repo)

            if tipo == Comprobante.TipoComprobante.FACTURA:
                comprobante = FacturaService.emitir(
                    empresa=empresa_domain,
                    cliente=cliente_domain,
                    detalles_data=detalles,
                    usuario_id=request.user.id,
                    comp_repo=comp_repo, num_repo=num_repo,
                    prod_repo=prod_repo, sunat_client=sunat_client
                )
            elif tipo == Comprobante.TipoComprobante.BOLETA:
                comprobante = BoletaService.emitir(
                    empresa=empresa_domain,
                    cliente=cliente_domain,
                    detalles_data=detalles,
                    usuario_id=request.user.id,
                    comp_repo=comp_repo, num_repo=num_repo,
                    prod_repo=prod_repo, sunat_client=sunat_client
                )
            else:
                raise ValueError("Tipo de comprobante no soportado.")
            return JsonResponse({
                'success': True,
                'message': f'Comprobante {comprobante.serie_numero} emitido correctamente.',
                'comprobante_id': comprobante.id,
                'serie_numero': comprobante.serie_numero,
                'estado': comprobante.estado,
            })
        except ComprobanteException as e:
            logger.exception(f"COMPROBANTE EXCEPTION: {e}")
            return JsonResponse({'success': False, 'error': str(e), 'codigo': getattr(e, 'codigo_error', 'ERR_DESCONOCIDO')}, status=400)
        except Exception as e:
            logger.exception(f"UNEXPECTED EXCEPTION: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    productos = Producto.objects.filter(activo=True)
    return render(request, 'comprobantes/emitir.html', {'productos': productos})


@login_required
def lista_comprobantes_view(request):
    """Lista de comprobantes con filtros."""
    qs = Comprobante.objects.select_related('cliente', 'empresa')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)

    # Filtros
    tipo = request.GET.get('tipo')
    estado = request.GET.get('estado')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    buscar = request.GET.get('buscar')

    orden = request.GET.get('orden', 'desc')

    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if fecha_desde:
        qs = qs.filter(fecha_emision__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_emision__lte=fecha_hasta)
    if buscar:
        qs = qs.filter(
            Q(cliente__razon_social__icontains=buscar) |
            Q(cliente__num_doc__icontains=buscar) |
            Q(serie__icontains=buscar)
        )

    if orden == 'asc':
        comprobantes = qs.order_by('fecha_emision', 'numero')[:100]
    else:
        comprobantes = qs.order_by('-fecha_emision', '-numero')[:100]

    return render(request, 'comprobantes/lista.html', {
        'comprobantes': comprobantes,
        'filtros': {'tipo': tipo, 'estado': estado, 'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta, 'buscar': buscar, 'orden': orden},
    })


@login_required
def detalle_comprobante_view(request, pk):
    qs = Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto', 'logs_envio')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    return render(request, 'comprobantes/detalle.html', {'comprobante': comprobante})


@login_required
def pdf_comprobante_view(request, pk):
    qs = Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    pdf_buffer = generar_pdf_comprobante(comprobante)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{comprobante.serie_numero}.pdf"'
    return response


@login_required
def descargar_xml_view(request, pk):
    """Descargar el XML firmado del comprobante."""
    qs = Comprobante.objects.all()
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    if not comprobante.xml_firmado:
        messages.error(request, 'Este comprobante aún no tiene un XML generado.')
        return redirect('comprobante-detalle', pk=pk)
        
    response = HttpResponse(comprobante.xml_firmado, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{comprobante.empresa.ruc}-{comprobante.tipo}-{comprobante.serie_numero}.xml"'
    return response

@login_required
def descargar_cdr_view(request, pk):
    """Descargar el CDR (.zip) devuelto por SUNAT."""
    qs = Comprobante.objects.all()
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    
    if comprobante.estado != 'ACEPTADO':
        messages.error(request, 'Este comprobante aún no ha sido aceptado por SUNAT, por lo que no tiene CDR.')
        return redirect('comprobante-detalle', pk=pk)
    
    import os
    from django.conf import settings
    
    TIPO_DOCUMENTO_SUNAT = {
        'FACTURA': '01',
        'BOLETA': '03',
        'NOTA_CREDITO': '07',
    }
    tipo_codigo = TIPO_DOCUMENTO_SUNAT.get(comprobante.tipo, '01')
    zip_file_name = f"R-{comprobante.empresa.ruc}-{tipo_codigo}-{comprobante.serie_numero}.zip"
    
    cdr_path = os.path.join(settings.BASE_DIR, 'cdrs', zip_file_name)
    
    if not os.path.exists(cdr_path):
        messages.error(request, 'El archivo CDR físico no se encuentra en el servidor.')
        return redirect('comprobante-detalle', pk=pk)
        
    with open(cdr_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{zip_file_name}"'
        return response

@csrf_exempt
@login_required
def nota_credito_view(request):
    """Formulario para emitir nota de crédito."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'No tiene permisos para emitir notas de crédito.'}, status=403)
        messages.error(request, 'No tiene permisos para acceder a esta página.')
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            empresa_django = request.user.empresa
            empresa_domain = DominioEmpresa(
                id=empresa_django.id, ruc=empresa_django.ruc,
                razon_social=empresa_django.razon_social, nombre_comercial=empresa_django.nombre_comercial,
                direccion=empresa_django.direccion, regimen_tributario=empresa_django.regimen_tributario
            )
            
            comp_repo = DjangoComprobanteRepository()
            num_repo = DjangoNumeracionRepository()
            sunat_client = DjangoSunatClient(comp_repo)
            
            comp_ref_domain = comp_repo.obtener_comprobante_por_id(data['comprobante_referencia_id'])

            comprobante_nc, nota = NotaCreditoService.emitir(
                empresa=empresa_domain,
                comprobante_ref=comp_ref_domain,
                motivo=data['motivo'],
                tipo_nota=data['tipo_nota'],
                monto_afectado=data['monto_afectado'],
                usuario_id=request.user.id,
                comp_repo=comp_repo, num_repo=num_repo,
                sunat_client=sunat_client
            )
            return JsonResponse({
                'success': True,
                'message': f'Nota de Crédito {comprobante_nc.serie_numero} emitida correctamente.',
                'comprobante_id': comprobante_nc.id,
            })
        except ComprobanteException as e:
            logger.exception(f"COMPROBANTE EXCEPTION NC: {e}")
            return JsonResponse({'success': False, 'error': str(e), 'codigo': getattr(e, 'codigo_error', 'ERR_DESCONOCIDO')}, status=400)
        except Exception as e:
            logger.exception(f"UNEXPECTED EXCEPTION NC: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'comprobantes/nota_credito.html', {
        'tipos_nota': list(dict(item) for item in [
            {'value': c[0], 'label': c[1]} for c in __import__('apps.comprobantes.models', fromlist=['NotaCredito']).NotaCredito.TipoNota.choices
        ]),
    })


@login_required
def reenviar_comprobante_view(request, pk):
    """Reenviar un comprobante rechazado."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        messages.error(request, 'No tiene permisos para reenviar comprobantes.')
        return redirect('dashboard')
        
    qs = Comprobante.objects.all()
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(creado_por=request.user)
        
    comprobante = get_object_or_404(qs, pk=pk)
    try:
        comp_repo = DjangoComprobanteRepository()
        sunat_client = DjangoSunatClient(comp_repo)
        
        comp_domain = comp_repo.obtener_comprobante_por_id(comprobante.id)
        
        # Recalcular totales con el código actual (por si hubo cambios en los impuestos)
        from dominio.comprobantes.servicios import TributaryEngine
        detalles_data = []
        productos_map = {}
        for det in comp_domain.detalles:
            detalles_data.append({
                'producto_id': det.producto_id,
                'cantidad': det.cantidad,
                'precio_unitario': det.precio_unitario,
                'descuento': det.descuento,
            })
            productos_map[det.producto_id] = det.producto
            
        totales = TributaryEngine.calcular_totales(detalles_data, productos_map)
        
        # 1. Actualizar dominio en memoria
        comp_domain.subtotal = totales['subtotal']
        comp_domain.total_inafecto = totales['total_inafecto']
        comp_domain.igv = totales['igv']
        comp_domain.total = totales['total']
        
        # 2. Actualizar base de datos de Django
        comprobante.subtotal = totales['subtotal']
        comprobante.total_inafecto = totales['total_inafecto']
        comprobante.igv = totales['igv']
        comprobante.total = totales['total']
        comprobante.save(update_fields=['subtotal', 'total_inafecto', 'igv', 'total'])
        
        django_detalles = list(comprobante.detalles.all().order_by('id'))
        
        for i, det_dict in enumerate(totales['lineas']):
            comp_domain.detalles[i].igv_linea = det_dict['igv_linea']
            comp_domain.detalles[i].subtotal = det_dict['subtotal']
            
            django_det = django_detalles[i]
            django_det.igv_linea = det_dict['igv_linea']
            django_det.subtotal = det_dict['subtotal']
            django_det.save(update_fields=['igv_linea', 'subtotal'])

        # 3. Regenerar el XML porque las matemáticas y etiquetas cambiaron
        xml_str, hash_cpe = sunat_client.generar_xml(comp_domain)
        comp_domain.xml_firmado = xml_str
        comp_domain.hash_cpe = hash_cpe
        
        comprobante.xml_firmado = xml_str
        comprobante.hash_cpe = hash_cpe
        comprobante.save(update_fields=['xml_firmado', 'hash_cpe'])

        sunat_client.enviar_comprobante(comp_domain)
        
        messages.success(request, f'Comprobante {comprobante.serie_numero} reenviado. Nuevo estado: {comp_domain.estado}')
    except ComprobanteException as e:
        messages.error(request, f'No se pudo reenviar: {str(e)}')
    except Exception as e:
        messages.error(request, f'No se pudo reenviar: {str(e)}')
    return redirect('comprobante-detalle', pk=pk)


@login_required
def buscar_cliente_api(request):
    """API interna para autocompletado de clientes."""
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse([], safe=False)
    clientes = Cliente.objects.filter(
        Q(num_doc__icontains=q) | Q(razon_social__icontains=q)
    )[:10]
    data = [{'id': c.id, 'num_doc': c.num_doc, 'tipo_doc': c.tipo_doc,
             'razon_social': c.razon_social, 'direccion': c.direccion} for c in clientes]
    return JsonResponse(data, safe=False)


@login_required
def buscar_comprobante_api(request):
    """API interna para buscar comprobante por serie-número."""
    serie_numero = request.GET.get('q', '')
    if '-' not in serie_numero:
        return JsonResponse({'found': False})
    parts = serie_numero.split('-')
    try:
        serie = parts[0]
        numero = int(parts[1])
        qs = Comprobante.objects.select_related('cliente')
        if request.user.empresa:
            qs = qs.filter(empresa=request.user.empresa)
        if request.user.is_emisor:
            qs = qs.filter(creado_por=request.user)
            
        comp = qs.get(serie=serie, numero=numero)
        return JsonResponse({
            'found': True,
            'id': comp.id,
            'serie_numero': comp.serie_numero,
            'tipo': comp.get_tipo_display(),
            'cliente': comp.cliente.razon_social,
            'total': str(comp.total),
            'estado': comp.estado,
        })
    except (Comprobante.DoesNotExist, ValueError, IndexError):
        return JsonResponse({'found': False})
