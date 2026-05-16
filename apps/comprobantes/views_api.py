"""API Views para comprobantes electrónicos."""
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Comprobante
from .serializers import (
    ComprobanteListSerializer, ComprobanteDetailSerializer,
    EmitirComprobanteSerializer, NotaCreditoInputSerializer,
)
from .filters import ComprobanteFilter
from .services import emitir_comprobante, emitir_nota_credito
from .sunat_client import reenviar_comprobante
from .pdf_generator import generar_pdf_comprobante
from apps.clientes.models import Cliente
from apps.accounts.permissions import IsEmisor, IsEmisorOrContador


class FacturaCreateView(APIView):
    """POST /api/facturas/ — Emitir factura con cálculo de IGV y XML mock."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente = Cliente.objects.get(id=serializer.validated_data['cliente_id'])
            comprobante = emitir_comprobante(
                empresa=request.user.empresa,
                cliente=cliente,
                tipo=Comprobante.TipoComprobante.FACTURA,
                detalles_data=serializer.validated_data['detalles'],
                usuario=request.user,
            )
            return Response(
                ComprobanteDetailSerializer(comprobante).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BoletaCreateView(APIView):
    """POST /api/boletas/ — Emitir boleta de venta."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente = Cliente.objects.get(id=serializer.validated_data['cliente_id'])
            comprobante = emitir_comprobante(
                empresa=request.user.empresa,
                cliente=cliente,
                tipo=Comprobante.TipoComprobante.BOLETA,
                detalles_data=serializer.validated_data['detalles'],
                usuario=request.user,
            )
            return Response(
                ComprobanteDetailSerializer(comprobante).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NotaCreditoCreateView(APIView):
    """POST /api/notas-credito/ — Emitir nota de crédito."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = NotaCreditoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            comp_ref = Comprobante.objects.get(
                id=serializer.validated_data['comprobante_referencia_id']
            )
            comprobante_nc, nota = emitir_nota_credito(
                empresa=request.user.empresa,
                comprobante_ref=comp_ref,
                motivo=serializer.validated_data['motivo'],
                tipo_nota=serializer.validated_data['tipo_nota'],
                monto_afectado=serializer.validated_data['monto_afectado'],
                usuario=request.user,
            )
            return Response(
                ComprobanteDetailSerializer(comprobante_nc).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ComprobanteListView(generics.ListAPIView):
    """GET /api/comprobantes/ — Listado con filtros."""
    serializer_class = ComprobanteListSerializer
    permission_classes = [IsAuthenticated, IsEmisorOrContador]
    filterset_class = ComprobanteFilter

    def get_queryset(self):
        qs = Comprobante.objects.select_related('cliente', 'empresa')
        if self.request.user.empresa:
            qs = qs.filter(empresa=self.request.user.empresa)
        if self.request.user.is_emisor:
            qs = qs.filter(created_by=self.request.user)
        return qs


class ComprobanteDetailView(generics.RetrieveAPIView):
    """GET /api/comprobantes/{id}/ — Detalle del comprobante."""
    serializer_class = ComprobanteDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles', 'logs_envio')


class ReenviarView(APIView):
    """POST /api/comprobantes/{id}/reenviar/ — Reenviar comprobante rechazado."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request, pk):
        comprobante = get_object_or_404(Comprobante, pk=pk)
        try:
            log = reenviar_comprobante(comprobante)
            comprobante.refresh_from_db()
            return Response(ComprobanteDetailSerializer(comprobante).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ComprobantePDFView(APIView):
    """GET /api/comprobantes/{id}/pdf/ — Descargar PDF del comprobante."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        comprobante = get_object_or_404(
            Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto'),
            pk=pk
        )
        pdf_buffer = generar_pdf_comprobante(comprobante)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{comprobante.serie_numero}.pdf"'
        return response
