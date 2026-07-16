"""Formularios Django para comprobantes."""
from django import forms
from apps.comprobantes.models import NotaCredito


class EmitirComprobanteForm(forms.Form):
    """Form base para emitir comprobantes (la lógica dinámica va con Alpine.js)."""
    TIPO_CHOICES = [('FACTURA', 'Factura'), ('BOLETA', 'Boleta')]
    tipo = forms.ChoiceField(choices=TIPO_CHOICES, widget=forms.Select(attrs={
        'class': 'form-select', 'x-model': 'tipo'
    }))
    cliente_id = forms.IntegerField(widget=forms.HiddenInput(attrs={'x-model': 'clienteId'}))


class NotaCreditoForm(forms.Form):
    """Formulario para emitir nota de crédito."""
    serie_numero = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Ej: F001-00001',
        }),
        label='Serie-Número del comprobante original'
    )
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Motivo'
    )
    tipo_nota = forms.ChoiceField(
        choices=NotaCredito.TipoNota.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Nota'
    )
    monto_afectado = forms.DecimalField(
        max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Monto Afectado (S/.)'
    )
