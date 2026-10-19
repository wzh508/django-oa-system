"""智能分析接口（创新点 6.3）。"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action

from apps.common.response import ok
from apps.common.viewsets import BaseViewSet

from . import services


class InsightViewSet(BaseViewSet):
    """审批时效预测 / 风险看板 / 瓶颈分析 / 分级催办。"""

    queryset = services.ApprovalSLAPredict.objects.none()
    perm_prefix = "insight"
    audit_module = "insight"
    open_actions = set()
    perm_map = {
        "refresh": "insight:sla:view",
        "risk": "insight:risk:view",
        "bottleneck": "insight:bottleneck:view",
        "stats": "insight:sla:view",
        "urge": "insight:risk:view",
    }
    # 聚合看板接口无模型序列化器，统一响应为 {code,msg,data} 信封，
    # 显式声明响应类型，避免 drf-spectacular 因取不到 serializer 而忽略本视图。
    serializer_class = serializers.Serializer
    _AGG_RESP = {200: OpenApiTypes.OBJECT}

    @extend_schema(summary="重算时效预测", responses=_AGG_RESP)
    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):
        n = services.refresh_predictions()
        return ok({"predicted": n, "at": services.timezone.now().isoformat()})

    @extend_schema(summary="风险看板", responses=_AGG_RESP)
    @action(detail=False, methods=["get"], url_path="risk")
    def risk(self, request):
        return ok(services.risk_dashboard())

    @extend_schema(summary="瓶颈分析", responses=_AGG_RESP)
    @action(detail=False, methods=["get"], url_path="bottleneck")
    def bottleneck(self, request):
        return ok(services.bottleneck_analysis())

    @extend_schema(summary="整体时效统计", responses=_AGG_RESP)
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        return ok(services.sla_stats())

    @extend_schema(summary="执行分级催办", responses=_AGG_RESP)
    @action(detail=False, methods=["post"], url_path="urge")
    def urge(self, request):
        d = request.data or {}
        result = services.graded_urge(
            overdue_threshold_hours=float(d.get("overdue_threshold_hours") or 0),
            warning_hours=float(d.get("warning_hours") or 24),
        )
        return ok(result)
