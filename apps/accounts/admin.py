from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'empresa', 'is_active')
    list_filter = ('rol', 'empresa', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Información del Sistema', {
            'fields': ('rol', 'empresa'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información del Sistema', {
            'fields': ('rol', 'empresa'),
        }),
    )
