"""审批流序列化器。"""
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.accounts.serializers import UserListSerializer

from .models import (
    ApprovalRecord,
    ApprovalSLAPredict,
    ApprovalTask,
    ExpenseRequest,
    FlowNode,
    UrgeRecord,
    WorkflowInstance,
    WorkflowReplayRun,
    WorkflowTemplate,
)


class FlowNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowNode
        fields = ["id", "name", "order", "node_type", "approver_source", "approver_ids",
                  "approver_role_codes", "approve_mode", "condition_expr", "allow_add",
                  "allow_transfer", "allow_revoke", "allow_urge", "sla_hours"]


class TemplateListSerializer(serializers.ModelSerializer):
    node_count = serializers.SerializerMethodField()
    instance_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowTemplate
        fields = ["id", "code", "name", "category", "version", "is_active", "is_published",
                  "description", "icon", "sort", "published_at", "node_count", "instance_count"]

    def get_node_count(self, obj) -> int:
        return obj.nodes.filter(is_deleted=False).count()

    def get_instance_count(self, obj) -> int:
        return WorkflowInstance.objects.filter(template=obj).count()


class TemplateDetailSerializer(TemplateListSerializer):
    nodes = serializers.SerializerMethodField()

    class Meta(TemplateListSerializer.Meta):
        fields = TemplateListSerializer.Meta.fields + ["form_schema", "nodes"]

    def get_nodes(self, obj):
        return FlowNodeSerializer(obj.nodes.filter(is_deleted=False).order_by("order", "id"), many=True).data


class TemplateWriteSerializer(serializers.ModelSerializer):
    nodes = FlowNodeSerializer(many=True, required=False)

    class Meta:
        model = WorkflowTemplate
        fields = ["id", "code", "name", "category", "description", "form_schema", "icon", "sort", "nodes"]

    def create(self, validated_data):
        nodes = validated_data.pop("nodes", [])
        tpl = WorkflowTemplate.objects.create(**validated_data)
        for i, n in enumerate(nodes):
            FlowNode.objects.create(template=tpl, order=n.get("order", i), **{
                k: v for k, v in n.items() if k != "order"
            })
        return tpl

    def update(self, instance, validated_data):
        nodes = validated_data.pop("nodes", None)
        tpl = super().update(instance, validated_data)
        if nodes is not None:
            FlowNode.objects.filter(template=tpl).delete()
            for i, n in enumerate(nodes):
                FlowNode.objects.create(template=tpl, order=n.get("order", i), **{
                    k: v for k, v in n.items() if k != "order"
                })
        return tpl


# 与 apps.schedule.serializers.TaskSerializer 同名，需显式区分 OpenAPI 组件名，否则 schema 生成冲突
@extend_schema_serializer(component_name="ApprovalTask")
class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.display_name", read_only=True, default="")
    instance_title = serializers.CharField(source="instance.title", read_only=True, default="")
    instance_code = serializers.CharField(source="instance.code", read_only=True, default="")
    applicant_name = serializers.CharField(source="instance.applicant.display_name", read_only=True, default="")
    category = serializers.CharField(source="instance.category", read_only=True, default="")
    overdue = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalTask
        fields = ["id", "instance", "instance_code", "instance_title", "applicant_name", "category",
                  "node_id", "node_name", "seq", "assignee", "assignee_name", "status", "mode",
                  "is_added", "comment", "assigned_at", "acted_at", "due_at", "sla_hours", "overdue"]

    def get_overdue(self, obj) -> bool:
        from django.utils import timezone

        return bool(obj.due_at and obj.due_at < timezone.now() and obj.status == "pending")


class RecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRecord
        fields = ["id", "created_at", "node_name", "action", "operator", "operator_name", "comment", "snapshot"]


class SLAPredictSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalSLAPredict
        fields = ["predicted_hours", "predicted_finish_at", "risk_level", "risk_score",
                  "sample_count", "top_features", "baseline_hours", "model_version", "created_at"]


class InstanceListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source="applicant.display_name", read_only=True, default="")
    dept_name = serializers.CharField(source="dept.name", read_only=True, default="")
    template_name = serializers.CharField(source="template.name", read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    risk_level = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowInstance
        fields = ["id", "code", "title", "template", "template_name", "template_version", "category",
                  "applicant", "applicant_name", "dept", "dept_name", "status", "status_display",
                  "current_node_name", "amount", "days", "urgency", "submitted_at", "finished_at", "risk_level"]

    def get_risk_level(self, obj) -> str:
        pred = getattr(obj, "sla_predict", None)
        return pred.risk_level if pred else ""


class InstanceDetailSerializer(InstanceListSerializer):
    form_data = serializers.JSONField()
    tasks = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()
    flow_nodes = serializers.SerializerMethodField()
    prediction = serializers.SerializerMethodField()

    class Meta(InstanceListSerializer.Meta):
        fields = InstanceListSerializer.Meta.fields + [
            "form_data", "attachment_ids", "current_seq", "template_snapshot", "tasks", "records",
            "flow_nodes", "prediction",
        ]

    def get_tasks(self, obj):
        return TaskSerializer(obj.tasks.filter(is_deleted=False).select_related("assignee").order_by("seq", "id"),
                              many=True).data

    def get_records(self, obj):
        return RecordSerializer(obj.records.all().order_by("id"), many=True).data

    def get_flow_nodes(self, obj):
        nodes = sorted(obj.snapshot_nodes, key=lambda x: x.get("order", 0))
        current = obj.current_seq
        tasks_by_seq = {}
        for t in obj.tasks.all():
            tasks_by_seq.setdefault(t.seq, []).append(t)
        out = []
        for n in nodes:
            seq = n.get("order", 0)
            ts = tasks_by_seq.get(seq, [])
            out.append({
                "order": seq,
                "name": n.get("name"),
                "node_type": n.get("node_type"),
                "approve_mode": n.get("approve_mode"),
                "condition_expr": n.get("condition_expr"),
                "status": "done" if seq < current else ("current" if seq == current else "todo"),
                "assignees": [{"id": t.assignee_id, "name": t.assignee.display_name, "status": t.status} for t in ts],
            })
        return out

    def get_prediction(self, obj):
        pred = getattr(obj, "sla_predict", None)
        return SLAPredictSerializer(pred).data if pred else None


class StartInstanceSerializer(serializers.Serializer):
    template_code = serializers.CharField()
    title = serializers.CharField()
    form_data = serializers.JSONField(default=dict, required=False)
    category = serializers.CharField(required=False, default="")
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    days = serializers.DecimalField(max_digits=10, decimal_places=1, required=False, allow_null=True)
    urgency = serializers.ChoiceField(choices=["low", "normal", "high"], default="normal", required=False)
    attachment_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class ActSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "transfer", "add_sign", "rollback"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    transfer_to = serializers.IntegerField(required=False, allow_null=True)
    add_user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class UrgeSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReplayRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowReplayRun
        fields = ["id", "template", "template_version", "since_days", "limit", "status",
                  "progress", "result", "cost_ms", "started_at", "finished_at", "created_at"]


class UrgeRecordSerializer(serializers.ModelSerializer):
    from_user_name = serializers.CharField(source="from_user.display_name", read_only=True, default="")
    to_user_name = serializers.CharField(source="to_user.display_name", read_only=True, default="")

    class Meta:
        model = UrgeRecord
        fields = ["id", "created_at", "instance", "from_user", "from_user_name", "to_user",
                  "to_user_name", "cc_user", "level", "channel", "content"]


# ------------------------------------------------------------------ 报销
class ExpenseListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source="applicant.display_name", read_only=True, default="")
    dept_name = serializers.CharField(source="dept.name", read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    fee_type_display = serializers.CharField(source="get_fee_type_display", read_only=True)
    pay_status_display = serializers.CharField(source="get_pay_status_display", read_only=True)
    instance_id = serializers.IntegerField(source="workflow_instance_id", read_only=True)

    class Meta:
        model = ExpenseRequest
        fields = ["id", "code", "title", "applicant", "applicant_name", "dept", "dept_name",
                  "status", "status_display", "current_node", "fee_type", "fee_type_display",
                  "amount", "invoice_count", "pay_status", "pay_status_display", "instance_id",
                  "submitted_at", "finished_at", "created_at", "updated_at"]


class ExpenseDetailSerializer(ExpenseListSerializer):
    items = serializers.JSONField()
    remark = serializers.CharField()
    instance = serializers.SerializerMethodField()

    class Meta(ExpenseListSerializer.Meta):
        fields = ExpenseListSerializer.Meta.fields + ["items", "remark", "instance"]

    def get_instance(self, obj):
        inst = obj.workflow_instance
        if not inst:
            return None
        return InstanceDetailSerializer(inst).data


class ExpenseWriteSerializer(serializers.ModelSerializer):
    items = serializers.JSONField(required=False, default=list)
    urgency = serializers.ChoiceField(choices=["low", "normal", "high"], default="normal", required=False)

    class Meta:
        model = ExpenseRequest
        fields = ["id", "title", "fee_type", "amount", "invoice_count", "items", "remark", "urgency"]

    def validate(self, attrs):
        items = attrs.get("items") or []
        if items and attrs.get("amount") is None:
            total = sum(float(i.get("amount") or 0) for i in items)
            if total <= 0:
                raise serializers.ValidationError("报销金额必须大于 0")
            attrs["amount"] = round(total, 2)
        if attrs.get("amount") is None or attrs.get("amount") <= 0:
            raise serializers.ValidationError("报销金额必须大于 0")
        if not attrs.get("title"):
            attrs["title"] = f"{dict(ExpenseRequest.FeeType.choices).get(attrs.get('fee_type'), '费用')}报销"
        return attrs

    def create(self, validated_data):
        validated_data.pop("urgency", None)
        return super().create(validated_data)
