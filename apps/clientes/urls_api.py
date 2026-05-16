"""URL patterns API para Clientes."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .serializers import ClienteViewSet

router = DefaultRouter()
router.register('clientes', ClienteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
