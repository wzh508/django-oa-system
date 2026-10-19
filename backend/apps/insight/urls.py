from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InsightViewSet

router = DefaultRouter()
router.register("", InsightViewSet, basename="insight")

urlpatterns = [path("", include(router.urls))]
