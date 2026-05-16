"""
URL configuration for facturacion_sunat project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Web Views ─────────────────────────────────────────────────
    path('', include('apps.comprobantes.urls_web')),
    path('accounts/', include('apps.accounts.urls')),
    path('empresas/', include('apps.empresa.urls_web')),
    path('clientes/', include('apps.clientes.urls_web')),
    path('productos/', include('apps.productos.urls_web')),
    path('reportes/', include('apps.reportes.urls_web')),

    # ── API REST ──────────────────────────────────────────────────
    path('api/', include('apps.comprobantes.urls_api')),
    path('api/', include('apps.clientes.urls_api')),
    path('api/', include('apps.productos.urls_api')),
    path('api/', include('apps.reportes.urls_api')),
    path('api/auth/', include('apps.accounts.urls_api')),

    # ── Swagger / OpenAPI ─────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
