"""审批流接口。"""
import logging

from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.common.exceptions import BusinessException, PermissionDeniedException
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet, BaseViewSet

from . import services
from .models import (
    ApprovalTask,
    ExpenseRequest,
    FlowNode,
    UrgeRecord,
    WorkflowInstance,
    WorkflowReplayRun,
    WorkflowTemplate,
)
from .replay import health_report, run_replay
from .serializers import (
    ActSerializer,
    ExpenseDetailSerializer,
    ExpenseListSerializer,
    ExpenseWriteSerializer,
    FlowNodeSerializer,
    InstanceDetailSerializer,
    InstanceListSerializer,
    ReplayRunSerializer,
    RecordSerializer,
    StartInstanceSerializer,
    TaskSerializer,
    TemplateDetailSerializer,
    TemplateListSerializer,
    TemplateWriteSerializer,
    UrgeRecordSerializer,
    UrgeSerializer,
)

logger = logging.getLogger(__name__)


class WorkflowTemplateViewSet(BaseModelViewSet):
    queryset = WorkflowTemplate.objects.all()
    perm_prefix = "workflow:template"
    audit_module = "workflow"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TemplateWriteSerializer
        return TemplateDetailSerializer if self.action == "retrieve" else TemplateListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("code"):
            qs = qs.filter(code=p.get("code"))
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("only_active") == "1":
            qs = qs.filter(is_active=True)
        return qs.order_by("code", "-version")

    @extend_schema(summary="发布模板（生成新版本）")
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        tpl = services.publish_template(int(pk), request.user)
        return ok({"id": tpl.id, "code": tpl.code, "version": tpl.version, "is_active": tpl.is_active})

    @extend_schema(summary="回滚到该历史版本")
    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, pk=None):
        tpl = services.rollback_template(int(pk), request.user)
        return ok({"id": tpl.id, "code": tpl.code, "version": tpl.version, "is_active": True})

    @extend_schema(summary="版本对比（diff）", description="GET /workflow/templates/{id}/diff/?other=<另一版本ID>")
    @action(detail=True, methods=["get"], url_path="diff")
    def diff(self, request, pk=None):
        other = request.query_params.get("other")
        if not other:
            raise BusinessException("缺少 other 参数（另一版本模板ID）", code=4001)
        return ok(services.diff_template(int(pk), int(other)))

    @extend_schema(summary="模板版本列表")
    @action(detail=False, methods=["get"], url_path="versions")
    def versions(self, request):
        code = request.query_params.get("code")
        if not code:
            raise BusinessException("缺少 code 参数", code=4001)
        rows = WorkflowTemplate.objects.filter(code=code).order_by("-version")
        return ok(TemplateListSerializer(rows, many=True).data)


class FlowNodeViewSet(BaseModelViewSet):
    queryset = FlowNode.objects.all().select_related("template")
    perm_prefix = "workflow:template"
    audit_module = "workflow"
    serializer_class = FlowNodeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tid = self.request.query_params.get("template_id")
        return qs.filter(template_id=tid) if tid else qs


class WorkflowInstanceViewSet(BaseModelViewSet):
    queryset = WorkflowInstance.objects.all().select_related("applicant", "dept", "template")
    perm_prefix = "workflow:instance"
    audit_module = "workflow"
    data_scope_resource = "workflow.instance"
    perm_map = {
        "start": "workflow:instance:create",
        "revoke": "workflow:instance:revoke",
        "urge": "workflow:instance:urge",
        "terminate": "workflow:instance:approve",
        "flow": "workflow:instance:retrieve",
    }

    def get_serializer_class(self):
        return InstanceDetailSerializer if self.action == "retrieve" else InstanceListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        user = self.request.user
        if not user.is_superuser and self.action == "list":
            qs = qs.filter(Q(applicant=user) | Q(tasks__assignee=user)).distinct()
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("mine") == "1":
            qs = qs.filter(applicant=user)
        if p.get("keyword"):
            kw = p.get("keyword")
            qs = qs.filter(Q(code__icontains=kw) | Q(title__icontains=kw))
        if p.get("date_from"):
            qs = qs.filter(submitted_at__date__gte=p.get("date_from"))
        if p.get("date_to"):
            qs = qs.filter(submitted_at__date__lte=p.get("date_to"))
        return qs.order_by("-id")

    @extend_schema(
        summary="发起申请",
        request=StartInstanceSerializer,
        examples=[OpenApiExample("请假示例", value={
            "template_code": "leave", "title": "年假申请 3 天",
            "form_data": {"start_at": "2026-09-25", "end_at": "2026-09-27", "reason": "家中有事"},
            "category": "leave", "days": 3, "urgency": "normal"})],
    )
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        ser = StartInstanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        instance = services.start_instance(
            applicant=request.user, template_code=d["template_code"], title=d["title"],
            form_data=d.get("form_data") or {}, category=d.get("category") or "",
            amount=d.get("amount"), days=d.get("days"), urgency=d.get("urgency") or "normal",
            attachment_ids=d.get("attachment_ids") or [],
        )
        return ok(InstanceDetailSerializer(instance).data)

    @extend_schema(summary="撤回申请")
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        instance = self.get_object()
        comment = (request.data or {}).get("comment", "")
        return ok(services.revoke_instance(instance.id, request.user, comment))

    @extend_schema(summary="催办")
    @action(detail=True, methods=["post"], url_path="urge")
    def urge(self, request, pk=None):
        instance = self.get_object()
        ser = UrgeSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        return ok(services.urge_instance(instance.id, request.user, ser.validated_data.get("comment", "")))

    @extend_schema(summary="终止流程（管理员）")
    @action(detail=True, methods=["post"], url_path="terminate")
    def terminate(self, request, pk=None):
        instance = self.get_object()
        comment = (request.data or {}).get("comment", "")
        return ok(services.terminate_instance(instance.id, request.user, comment))

    @extend_schema(summary="流程节点图（当前节点高亮）")
    @action(detail=True, methods=["get"], url_path="flow")
    def flow(self, request, pk=None):
        instance = self.get_object()
        return ok(InstanceDetailSerializer(instance).data["flow_nodes"])


class ApprovalTaskViewSet(BaseModelViewSet):
    queryset = ApprovalTask.objects.all().select_related("assignee", "instance", "instance__applicant")
    perm_prefix = "workflow:task"
    audit_module = "workflow"
    serializer_class = TaskSerializer
    perm_map = {
        "act": "workflow:instance:approve",
        "batch_approve": "workflow:instance:approve",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        p = self.request.query_params
        kind = p.get("kind", "todo")
        if kind == "todo":
            qs = qs.filter(assignee=user, status=ApprovalTask.Status.PENDING)
        elif kind == "done":
            qs = qs.filter(assignee=user).exclude(status=ApprovalTask.Status.PENDING)
        elif kind == "all" and not user.is_superuser:
            qs = qs.filter(assignee=user)
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("overdue") == "1":
            qs = qs.filter(status=ApprovalTask.Status.PENDING, due_at__lt=timezone.now())
        return qs.order_by("-assigned_at")

    @extend_schema(
        summary="审批操作",
        request=ActSerializer,
        description="支持 approve / reject / transfer / add_sign / rollback；并发安全（行锁）",
    )
    @action(detail=True, methods=["post"], url_path="act")
    def act(self, request, pk=None):
        ser = ActSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        result = services.act_on_task(
            int(pk), request.user, d["action"], d.get("comment", ""),
            transfer_to=d.get("transfer_to"), add_user_ids=d.get("add_user_ids") or [],
        )
        return ok(result)

    @extend_schema(summary="批量同意")
    @action(detail=False, methods=["post"], url_path="batch-approve")
    def batch_approve(self, request):
        ids = (request.data or {}).get("task_ids", [])
        comment = (request.data or {}).get("comment", "")
        results = []
        for tid in ids:
            try:
                results.append({"task_id": tid, **services.act_on_task(int(tid), request.user, "approve", comment)})
            except Exception as exc:
                results.append({"task_id": tid, "error": str(exc)})
        return ok({"results": results})


class WorkflowReplayViewSet(BaseViewSet):
    """流程沙盘回放（创新点 6.2）。"""

    queryset = WorkflowReplayRun.objects.none()
    perm_prefix = "workflow:replay"
    audit_module = "workflow"
    serializer_class = ReplayRunSerializer

    @extend_schema(summary="执行流程沙盘回放",
                   description="把历史单据放到指定模板版本上重放，输出瓶颈节点 TOP3 与优化建议")
    @action(detail=False, methods=["post"], url_path="run")
    def run(self, request):
        d = request.data or {}
        template_id = d.get("template_id")
        if not template_id:
            raise BusinessException("缺少 template_id", code=4001)
        run_obj = run_replay(
            int(template_id),
            since_days=int(d.get("since_days") or 90),
            limit=int(d.get("limit") or 500),
            operator=request.user,
        )
        return ok(ReplayRunSerializer(run_obj).data)

    @action(detail=False, methods=["get"], url_path="reports")
    def reports(self, request):
        rows = WorkflowReplayRun.objects.all().order_by("-id")[:20]
        return ok(ReplayRunSerializer(rows, many=True).data)

    @action(detail=True, methods=["get"], url_path="result")
    def result(self, request, pk=None):
        run_obj = WorkflowReplayRun.objects.filter(id=pk).first()
        if run_obj is None:
            raise BusinessException("回放任务不存在", code=4040, status_code=404)
        return ok(run_obj.result)


class WorkflowHealthViewSet(BaseViewSet):
    """流程健康度看板（创新点 6.2）。"""

    queryset = WorkflowReplayRun.objects.none()
    perm_prefix = "workflow:replay"
    audit_module = "workflow"
    serializer_class = ReplayRunSerializer
    open_actions = {"report"}

    @extend_schema(summary="流程健康度报告")
    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request):
        days = int(request.query_params.get("days") or 180)
        return ok(health_report(days))


class UrgeRecordViewSet(BaseViewSet):
    queryset = UrgeRecord.objects.all().select_related("from_user", "to_user")
    perm_prefix = "workflow:instance"
    audit_module = "workflow"
    serializer_class = UrgeRecordSerializer

    def list(self, request, *args, **kwargs):
        qs = self.queryset.order_by("-id")[:100]
        return ok(UrgeRecordSerializer(qs, many=True).data)


# ------------------------------------------------------------------ 报销
class ExpenseRequestViewSet(BaseModelViewSet):
    """费用报销：创建即发起审批流，审批完成后由信号回写状态。"""

    queryset = ExpenseRequest.objects.all().select_related("applicant", "dept", "workflow_instance")
    perm_prefix = "expense"
    audit_module = "expense"
    data_scope_resource = "workflow.instance"
    perm_map = {
        "create": "expense:apply",
        "list": "expense:list",
        "retrieve": "expense:list",
        "timeline": "expense:list",
        "audit": "expense:audit",
        "pay": "expense:pay",
        "stats": "expense:stats",
    }

    def get_serializer_class(self):
        if self.action == "create":
            return ExpenseWriteSerializer
        return ExpenseDetailSerializer if self.action == "retrieve" else ExpenseListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        p = self.request.query_params
        if not user.is_superuser and self.action == "list":
            if not (user.has_perm("expense:audit") or user.has_perm("expense:pay") or user.has_perm("expense:stats")):
                qs = qs.filter(applicant=user)
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("fee_type"):
            qs = qs.filter(fee_type=p.get("fee_type"))
        if p.get("pay_status"):
            qs = qs.filter(pay_status=p.get("pay_status"))
        if p.get("mine") == "1":
            qs = qs.filter(applicant=user)
        return qs.order_by("-id")

    def check_data_scope(self, obj) -> None:
        """对象级校验：非特权角色只能访问本人报销单。"""
        from rest_framework.exceptions import PermissionDenied

        user = self.request.user
        if user.is_superuser:
            return
        if user.has_perm("expense:audit") or user.has_perm("expense:pay") or user.has_perm("expense:stats"):
            return
        if obj.applicant_id != user.id:
            raise PermissionDenied("无权访问该报销单")

    def perform_create(self, serializer):
        validated = serializer.validated_data
        urgency = validated.get("urgency") or "normal"
        items = validated.get("items") or []
        from uuid import uuid4

        code = f"EXP{timezone.now().strftime('%Y%m%d')}{uuid4().hex[:8].upper()}"
        instance = serializer.save(applicant=self.request.user, dept=self.request.user.dept, code=code,
                                   status=ExpenseRequest.Status.DRAFT, created_by=self.request.user)
        wf = services.start_instance(
            applicant=self.request.user, template_code="expense", title=instance.title,
            form_data={"fee_type": instance.fee_type, "invoice_count": instance.invoice_count, "items": items,
                       "remark": instance.remark or ""},
            category="expense", amount=instance.amount, urgency=urgency, attachment_ids=[],
        )
        instance.workflow_instance = wf
        instance.status = ExpenseRequest.Status.PENDING
        instance.current_node = wf.current_node_name or ""
        instance.submitted_at = wf.submitted_at
        instance.save(update_fields=["workflow_instance", "status", "current_node", "submitted_at"])

    @extend_schema(summary="报销审核（同意/驳回）", request=ActSerializer)
    @action(detail=True, methods=["post"], url_path="audit")
    def audit(self, request, pk=None):
        expense = self.get_object()
        ser = ActSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        inst = expense.workflow_instance
        if inst is None:
            raise BusinessException("该报销单尚未关联审批流程", code=4001)
        task = ApprovalTask.objects.filter(instance=inst, assignee=request.user,
                                          status=ApprovalTask.Status.PENDING).first()
        if task is None:
            raise PermissionDeniedException("当前没有待您处理的审批任务")
        return ok(services.act_on_task(task.id, request.user, d["action"], d.get("comment", ""),
                                       transfer_to=d.get("transfer_to"), add_user_ids=d.get("add_user_ids") or []))

    @extend_schema(summary="支付确认")
    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        expense = self.get_object()
        if expense.status != ExpenseRequest.Status.APPROVED:
            raise BusinessException("仅审批通过的报销单可支付", code=4001)
        expense.pay_status = ExpenseRequest.PayStatus.PAID
        expense.paid_at = timezone.now()
        expense.paid_by = request.user
        expense.save(update_fields=["pay_status", "paid_at", "paid_by"])
        return ok(ExpenseDetailSerializer(expense).data)

    @extend_schema(summary="报销审批时间线")
    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        expense = self.get_object()
        inst = expense.workflow_instance
        records = inst.records.all().order_by("id") if inst else []
        return ok(RecordSerializer(records, many=True).data)

    @extend_schema(summary="报销统计")
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        from django.db.models import Sum

        qs = ExpenseRequest.objects.all()
        total_amount = qs.aggregate(s=Sum("amount"))["s"] or 0
        by_type = list(qs.values("fee_type").annotate(total=Sum("amount"), count=Count("id")).order_by("-total"))
        by_status = list(qs.values("status").annotate(total=Sum("amount"), count=Count("id")))
        by_pay = list(qs.values("pay_status").annotate(total=Sum("amount"), count=Count("id")))
        pending = qs.filter(status=ExpenseRequest.Status.PENDING).count()
        approved = qs.filter(status=ExpenseRequest.Status.APPROVED).count()
        paid = qs.filter(pay_status=ExpenseRequest.PayStatus.PAID).count()
        unpaid_amount = qs.filter(pay_status=ExpenseRequest.PayStatus.UNPAID,
                                  status=ExpenseRequest.Status.APPROVED).aggregate(s=Sum("amount"))["s"] or 0
        return ok({
            "total_amount": float(total_amount),
            "by_type": by_type,
            "by_status": by_status,
            "by_pay": by_pay,
            "pending": pending, "approved": approved, "paid": paid,
            "unpaid_amount": float(unpaid_amount),
        })
