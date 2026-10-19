from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalTaskViewSet,
    ExpenseRequestViewSet,
    FlowNodeViewSet,
    UrgeRecordViewSet,
    WorkflowHealthViewSet,
    WorkflowInstanceViewSet,
    WorkflowReplayViewSet,
    WorkflowTemplateViewSet,
)

router = DefaultRouter()
router.register("templates", WorkflowTemplateViewSet, basename="wf-template")
router.register("nodes", FlowNodeViewSet, basename="wf-node")
router.register("instances", WorkflowInstanceViewSet, basename="wf-instance")
router.register("tasks", ApprovalTaskViewSet, basename="wf-task")
router.register("replay", WorkflowReplayViewSet, basename="wf-replay")
router.register("health", WorkflowHealthViewSet, basename="wf-health")
router.register("urges", UrgeRecordViewSet, basename="wf-urge")
router.register("requests", ExpenseRequestViewSet, basename="wf-expense")

urlpatterns = [path("", include(router.urls))]
