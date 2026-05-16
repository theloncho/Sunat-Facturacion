from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Usuario personalizado con roles para el sistema de facturación.
    Roles:
      - ADMIN: Acceso total, gestión de usuarios y empresa.
      - EMISOR: Puede emitir comprobantes y ver los propios.
      - CONTADOR: Puede ver todos los comprobantes y generar reportes.
    """

    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        EMISOR = 'EMISOR', 'Emisor'
        CONTADOR = 'CONTADOR', 'Contador'

    rol = models.CharField(
        max_length=10,
        choices=Rol.choices,
        default=Rol.EMISOR,
        verbose_name='Rol'
    )
    empresa = models.ForeignKey(
        'empresa.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios',
        verbose_name='Empresa'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.rol})"

    @property
    def is_admin(self):
        return self.rol == self.Rol.ADMIN

    @property
    def is_emisor(self):
        return self.rol == self.Rol.EMISOR

    @property
    def is_contador(self):
        return self.rol == self.Rol.CONTADOR
