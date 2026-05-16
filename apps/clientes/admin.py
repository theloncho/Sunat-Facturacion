from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('num_doc', 'tipo_doc', 'razon_social', 'email')
    search_fields = ('num_doc', 'razon_social', 'email')
    list_filter = ('tipo_doc',)
