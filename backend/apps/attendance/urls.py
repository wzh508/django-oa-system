from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceExceptionViewSet,
    AttendanceRecordViewSet,
    AttendanceRuleViewSet,
    AttendanceSummaryViewSet,
    PunchViewSet,
)

router = DefaultRouter()
router.register("rules", AttendanceRuleViewSet, basename="att-rule")
router.register("punch", PunchViewSet, basename="att-punch")
router.register("records", AttendanceRecordViewSet, basename="att-record")
router.register("exceptions", AttendanceExceptionViewSet, basename="att-exception")
router.register("summary", AttendanceSummaryViewSet, basename="att-summary")

urlpatterns = [path("", include(router.urls))]
