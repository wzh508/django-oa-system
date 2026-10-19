"""人事域路由。"""
from rest_framework.routers import DefaultRouter

from .views import AnalyticsViewSet, ContractViewSet, StaffProfileViewSet, TrainingViewSet, TransferViewSet

router = DefaultRouter()
router.register(r"staff", StaffProfileViewSet, basename="hr-staff")
router.register(r"transfers", TransferViewSet, basename="hr-transfer")
router.register(r"contracts", ContractViewSet, basename="hr-contract")
router.register(r"trainings", TrainingViewSet, basename="hr-training")
router.register(r"analytics", AnalyticsViewSet, basename="hr-analytics")
urlpatterns = router.urls
