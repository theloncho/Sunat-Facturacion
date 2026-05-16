"""URL patterns API para Productos."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .serializers import ProductoViewSet

router = DefaultRouter()
router.register('productos', ProductoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
