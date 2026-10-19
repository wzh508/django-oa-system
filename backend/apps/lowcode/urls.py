from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DynamicRecordViewSet, FormSchemaViewSet

router = DefaultRouter()
router.register("schemas", FormSchemaViewSet, basename="lc-schema")
router.register("records", DynamicRecordViewSet, basename="lc-record")

urlpatterns = [path("", include(router.urls))]
