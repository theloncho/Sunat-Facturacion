"""Permisos personalizados basados en roles del sistema."""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'ADMIN'


class IsEmisor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ['EMISOR', 'ADMIN']


class IsContador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ['CONTADOR', 'ADMIN']


class IsEmisorOrContador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ['EMISOR', 'CONTADOR', 'ADMIN']
