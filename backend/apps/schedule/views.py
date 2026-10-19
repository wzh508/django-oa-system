"""日程与任务域接口。"""
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.common.exceptions import BusinessException
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet

from .models import Schedule, Task
from .serializers import ScheduleSerializer, TaskSerializer


class ScheduleViewSet(BaseModelViewSet):
    """日程管理。"""
    queryset = Schedule.objects.all().select_related("owner").prefetch_related("participants")
    perm_prefix = "schedule"
    audit_module = "schedule"
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("owner_id"):
            qs = qs.filter(owner_id=p.get("owner_id"))
        if p.get("from"):
            qs = qs.filter(start__gte=p.get("from"))
        if p.get("to"):
            qs = qs.filter(end__lte=p.get("to"))
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskViewSet(BaseModelViewSet):
    """看板任务。"""
    queryset = Task.objects.all().select_related("assignee", "creator")
    perm_prefix = "task"
    audit_module = "schedule"
    serializer_class = TaskSerializer
    perm_map = {"progress": "task:update"}

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("priority"):
            qs = qs.filter(priority=p.get("priority"))
        if p.get("assignee_id"):
            qs = qs.filter(assignee_id=p.get("assignee_id"))
        return qs

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @extend_schema(summary="更新进度", description="progress 0-100，达 100 自动置为已完成")
    @action(detail=True, methods=["post"])
    def progress(self, request, pk=None):
        t = self.get_object()
        try:
            val = int((request.data or {}).get("progress", t.progress))
        except (TypeError, ValueError):
            raise BusinessException("进度必须为整数", code=4001)
        val = max(0, min(100, val))
        t.progress = val
        if val >= 100:
            t.status = Task.Status.DONE
        t.save(update_fields=["progress", "status"])
        return ok({"id": t.id, "progress": t.progress, "status": t.status})
