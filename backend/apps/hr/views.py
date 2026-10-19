"""人事域接口。"""
from django.db.models import Count
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action

from apps.accounts.models import User
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet, BaseViewSet

from .models import Contract, StaffProfile, Training, Transfer
from .serializers import (ContractSerializer, StaffProfileSerializer, TrainingSerializer,
                          TransferSerializer)


class StaffProfileViewSet(BaseModelViewSet):
    """员工档案（敏感字段出口脱敏）。"""
    queryset = StaffProfile.objects.all().select_related("user", "user__dept")
    perm_prefix = "hr:staff"
    audit_module = "hr"
    serializer_class = StaffProfileSerializer
    perm_map = {"create": "hr:staff:update"}

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("dept_id"):
            qs = qs.filter(user__dept_id=p.get("dept_id"))
        if p.get("keyword"):
            qs = qs.filter(user__first_name__icontains=p.get("keyword"))
        return qs


class TransferViewSet(BaseModelViewSet):
    """入转调离。"""
    queryset = Transfer.objects.all().select_related("employee", "from_dept", "to_dept",
                                                    "from_position", "to_position", "handler")
    perm_prefix = "hr:transfer"
    audit_module = "hr"
    serializer_class = TransferSerializer

    def perform_create(self, serializer):
        serializer.save(handler=self.request.user)


class ContractViewSet(BaseModelViewSet):
    """劳动合同。"""
    queryset = Contract.objects.all().select_related("employee")
    perm_prefix = "hr:contract"
    audit_module = "hr"
    serializer_class = ContractSerializer


class TrainingViewSet(BaseModelViewSet):
    """培训记录。"""
    queryset = Training.objects.all().select_related("employee")
    perm_prefix = "hr:training"
    audit_module = "hr"
    serializer_class = TrainingSerializer


class AnalyticsViewSet(BaseViewSet):
    """员工结构分析（聚合看板）。"""
    perm_prefix = "hr:analytics"
    audit_module = "hr"
    queryset = StaffProfile.objects.none()
    perm_map = {"structure": "hr:analytics:view"}
    # 聚合看板无模型序列化器，声明响应类型即可，避免被 drf-spectacular 忽略
    serializer_class = serializers.Serializer

    @extend_schema(summary="员工结构分析", responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["get"])
    def structure(self, request):
        by_dept = list(User.objects.filter(is_active=True).values("dept__name")
                      .annotate(total=Count("id")).order_by("-total"))
        by_status = list(User.objects.filter(is_active=True).values("status")
                        .annotate(total=Count("id")))
        by_education = list(StaffProfile.objects.values("education")
                           .annotate(total=Count("id")).order_by("-total"))
        return ok({
            "total": User.objects.filter(is_active=True).count(),
            "by_dept": by_dept,
            "by_status": by_status,
            "by_education": by_education,
        })
