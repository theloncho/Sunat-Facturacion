"""Formularios Django para Empresa."""
from django import forms
from .models import Empresa


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['ruc', 'razon_social', 'nombre_comercial', 'direccion', 'regimen_tributario']
        widgets = {
            'ruc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUC de 11 dígitos'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razón Social de la empresa'}),
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre Comercial (Opcional)'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Dirección fiscal completa'}),
            'regimen_tributario': forms.Select(attrs={'class': 'form-select'}),
        }
