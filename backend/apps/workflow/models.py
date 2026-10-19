"""审批流引擎模型。

设计要点：
- 流程模板每次发布生成新版本；流程实例创建时冻结当时的模板快照（版本快照隔离）。
- 审批历史（ApprovalRecord）只追加，不修改不删除。
- 状态机显式定义，非法迁移直接拒绝。
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class WorkflowTemplate(BaseModel):
    """流程模板。每次发布生成新版本，历史版本保留以便对比与回滚。"""

    class Category(models.TextChoices):
        LEAVE = "leave", "请假"
        OVERTIME = "overtime", "加班"
        TRIP = "trip", "出差"
        CARD = "card", "补卡"
        EXPENSE = "expense", "报销"
        PURCHASE = "purchase", "采购"
        SEAL = "seal", "用印"
        CONTRACT = "contract", "合同"
        DYNAMIC = "dynamic", "自定义（低代码）"

    code = models.CharField("模板编码", max_length=64, db_index=True)
    name = models.CharField("模板名称", max_length=128)
    category = models.CharField("单据类型", max_length=32, choices=Category.choices, default=Category.LEAVE)
    version = models.IntegerField("版本", default=1)
    is_active = models.BooleanField("是否启用（当前生效版本）", default=False, db_index=True)
    is_published = models.BooleanField("是否已发布", default=False)
    description = models.CharField("说明", max_length=255, blank=True, default="")
    form_schema = models.JSONField("表单定义", default=list, blank=True,
                                   help_text="前端动态表单渲染用的字段定义，低代码配置可直接覆盖")
    icon = models.CharField("图标", max_length=64, blank=True, default="")
    sort = models.IntegerField("排序", default=0)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="published_templates")

    class Meta:
        verbose_name = "流程模板"
        verbose_name_plural = "流程模板"
        unique_together = ("code", "version")
        ordering = ["code", "-version"]
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self):
        return f"{self.name} v{self.version}"

    def snapshot(self) -> dict:
        """生成模板快照（节点序列 + 表单定义），随流程实例永久冻结。"""
        nodes = FlowNode.objects.filter(template=self, is_deleted=False).order_by("order", "id")
        return {
            "template_id": self.id,
            "template_code": self.code,
            "template_name": self.name,
            "version": self.version,
            "category": self.category,
            "form_schema": self.form_schema,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "order": n.order,
                    "node_type": n.node_type,
                    "approver_source": n.approver_source,
                    "approver_ids": n.approver_ids or [],
                    "approver_role_codes": n.approver_role_codes or [],
                    "approve_mode": n.approve_mode,
                    "condition_expr": n.condition_expr,
                    "allow_add": n.allow_add,
                    "allow_transfer": n.allow_transfer,
                    "allow_revoke": n.allow_revoke,
                    "allow_urge": n.allow_urge,
                    "sla_hours": n.sla_hours,
                }
                for n in nodes
            ],
        }


class FlowNode(BaseModel):
    """流程节点。"""

    class NodeType(models.TextChoices):
        START = "start", "开始"
        APPROVAL = "approval", "审批"
        CONDITION = "condition", "条件分支"
        END = "end", "结束"

    class ApproverSource(models.TextChoices):
        USER = "USER", "指定用户"
        ROLE = "ROLE", "指定角色"
        LEADER = "LEADER", "发起人直属上级"
        DEPT_HEAD = "DEPT_HEAD", "部门负责人"
        HR = "HR", "人力资源"
        FINANCE = "FINANCE", "财务"
        ADMIN = "ADMIN", "系统管理员"

    class ApproveMode(models.TextChoices):
        ALL = "ALL", "会签（全部同意）"
        ANY = "ANY", "或签（任一同意）"

    template = models.ForeignKey(WorkflowTemplate, verbose_name="所属模板", on_delete=models.CASCADE,
                                 related_name="nodes", db_index=True)
    name = models.CharField("节点名称", max_length=64)
    order = models.IntegerField("顺序", default=0, db_index=True)
    node_type = models.CharField("节点类型", max_length=16, choices=NodeType.choices, default=NodeType.APPROVAL)
    approver_source = models.CharField("审批人来源", max_length=16, choices=ApproverSource.choices, default=ApproverSource.LEADER)
    approver_ids = models.JSONField("指定审批人", default=list, blank=True)
    approver_role_codes = models.JSONField("指定角色编码", default=list, blank=True)
    approve_mode = models.CharField("审批模式", max_length=8, choices=ApproveMode.choices, default=ApproveMode.ANY)
    condition_expr = models.CharField("条件表达式", max_length=255, blank=True, default="",
                                      help_text="如 days > 3 ；为空表示无条件")
    allow_add = models.BooleanField("允许加签", default=True)
    allow_transfer = models.BooleanField("允许转办", default=True)
    allow_revoke = models.BooleanField("允许撤回", default=True)
    allow_urge = models.BooleanField("允许催办", default=True)
    sla_hours = models.IntegerField("节点时限（小时）", default=24)

    class Meta:
        verbose_name = "流程节点"
        verbose_name_plural = "流程节点"
        ordering = ["order", "id"]


class BaseRequest(BaseModel):
    """业务单据抽象基类：单号、状态、当前节点、提交时间、发起人 + 关联流程实例。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "审批中"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        REVOKED = "revoked", "已撤回"
        TERMINATED = "terminated", "已终止"

    code = models.CharField("单号", max_length=32, unique=True, db_index=True)
    title = models.CharField("标题", max_length=255, blank=True, default="")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="发起人", on_delete=models.CASCADE,
                                  related_name="%(class)s_requests", db_index=True)
    dept = models.ForeignKey("accounts.Department", verbose_name="所属部门", null=True, blank=True,
                             on_delete=models.SET_NULL)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    current_node = models.CharField("当前节点", max_length=64, blank=True, default="")
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    workflow_instance = models.OneToOneField("workflow.WorkflowInstance", verbose_name="流程实例",
                                             null=True, blank=True, on_delete=models.SET_NULL,
                                             related_name="%(class)s_request")
    form_data = models.JSONField("表单数据", default=dict, blank=True)
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, null=True, blank=True)
    days = models.DecimalField("天数/时长", max_digits=10, decimal_places=1, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.code} {self.title}"


class WorkflowInstance(BaseModel):
    """流程实例。创建时冻结模板快照，之后改模板不影响在途单据。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "审批中"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        REVOKED = "revoked", "已撤回"
        TERMINATED = "terminated", "已终止"

    code = models.CharField("流程单号", max_length=32, unique=True, db_index=True)
    title = models.CharField("标题", max_length=255)
    template = models.ForeignKey(WorkflowTemplate, verbose_name="流程模板", null=True, on_delete=models.SET_NULL)
    template_version = models.IntegerField("模板版本", default=1)
    template_snapshot = models.JSONField("模板快照", default=dict, blank=True,
                                         help_text="创建时冻结的节点序列，保证在途单据不受模板变更影响")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="发起人", on_delete=models.CASCADE,
                                  related_name="workflow_instances", db_index=True)
    dept = models.ForeignKey("accounts.Department", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    category = models.CharField("单据类型", max_length=32, default="leave", db_index=True)
    current_node_id = models.BigIntegerField("当前节点ID", null=True, blank=True)
    current_node_name = models.CharField("当前节点名称", max_length=64, blank=True, default="")
    current_seq = models.IntegerField("当前节点序号", default=0)
    form_data = models.JSONField("表单数据", default=dict, blank=True)
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, null=True, blank=True)
    days = models.DecimalField("天数", max_digits=10, decimal_places=1, null=True, blank=True)
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    urgency = models.CharField("紧急程度", max_length=16, default="normal",
                               choices=[("low", "低"), ("normal", "普通"), ("high", "高")])
    attachment_ids = models.JSONField("附件", default=list, blank=True)

    class Meta:
        verbose_name = "流程实例"
        verbose_name_plural = "流程实例"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["applicant", "status"]),
            models.Index(fields=["submitted_at"]),
        ]

    def __str__(self):
        return f"{self.code} {self.title}"

    @property
    def snapshot_nodes(self) -> list:
        return (self.template_snapshot or {}).get("nodes", [])

    def node_by_seq(self, seq: int):
        nodes = self.snapshot_nodes
        for n in nodes:
            if n.get("order") == seq:
                return n
        ordered = sorted(nodes, key=lambda x: x.get("order", 0))
        return ordered[seq] if 0 <= seq < len(ordered) else None


class ApprovalTask(BaseModel):
    """审批任务（待办 / 已办）。"""

    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已同意"
        REJECTED = "rejected", "已驳回"
        TRANSFERRED = "transferred", "已转办"
        ADDED = "added", "已加签"
        CANCELLED = "cancelled", "已取消"

    instance = models.ForeignKey(WorkflowInstance, verbose_name="流程实例", on_delete=models.CASCADE,
                                 related_name="tasks", db_index=True)
    node_id = models.BigIntegerField("节点ID", null=True, blank=True)
    node_name = models.CharField("节点名称", max_length=64)
    seq = models.IntegerField("节点序号", default=0, db_index=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="审批人", on_delete=models.CASCADE,
                                 related_name="approval_tasks", db_index=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    mode = models.CharField("审批模式", max_length=8, default="ANY")
    is_added = models.BooleanField("加签任务", default=False)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="added_tasks")
    transferred_from = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="transferred_tasks")
    comment = models.CharField("审批意见", max_length=512, blank=True, default="")
    assigned_at = models.DateTimeField("分配时间", default=timezone.now, db_index=True)
    acted_at = models.DateTimeField("处理时间", null=True, blank=True)
    due_at = models.DateTimeField("应完成时间", null=True, blank=True)
    sla_hours = models.IntegerField("节点时限", default=24)

    class Meta:
        verbose_name = "审批任务"
        verbose_name_plural = "审批任务"
        ordering = ["seq", "id"]
        indexes = [models.Index(fields=["assignee", "status"])]


class ApprovalRecord(models.Model):
    """审批历史：只追加，不修改、不删除。"""

    class Action(models.TextChoices):
        SUBMIT = "submit", "提交"
        APPROVE = "approve", "同意"
        REJECT = "reject", "驳回"
        TRANSFER = "transfer", "转办"
        ADD_SIGN = "add_sign", "加签"
        REVOKE = "revoke", "撤回"
        URGE = "urge", "催办"
        ROLLBACK = "rollback", "退回上一节点"
        TERMINATE = "terminate", "终止"
        AUTO_PASS = "auto_pass", "自动通过"

    created_at = models.DateTimeField("时间", default=timezone.now, db_index=True)
    instance = models.ForeignKey(WorkflowInstance, verbose_name="流程实例", on_delete=models.CASCADE,
                                 related_name="records", db_index=True)
    task = models.ForeignKey(ApprovalTask, null=True, blank=True, on_delete=models.SET_NULL, related_name="records")
    node_name = models.CharField("节点名称", max_length=64, blank=True, default="")
    action = models.CharField("动作", max_length=16, choices=Action.choices)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="approval_records")
    operator_name = models.CharField("操作人", max_length=64, blank=True, default="")
    comment = models.CharField("意见", max_length=512, blank=True, default="")
    snapshot = models.JSONField("当时快照", default=dict, blank=True)

    class Meta:
        verbose_name = "审批历史"
        verbose_name_plural = "审批历史"
        ordering = ["id"]


class ApprovalSLAPredict(models.Model):
    """审批时效预测结果（创新点 6.3）。"""

    created_at = models.DateTimeField("预测时间", default=timezone.now, db_index=True)
    instance = models.OneToOneField(WorkflowInstance, on_delete=models.CASCADE, related_name="sla_predict")
    predicted_hours = models.FloatField("预计剩余时长（小时）", default=0)
    predicted_finish_at = models.DateTimeField("预计完成时间", null=True, blank=True)
    risk_level = models.CharField("风险等级", max_length=8, default="low",
                                  choices=[("low", "低"), ("medium", "中"), ("high", "高")])
    risk_score = models.FloatField("风险分", default=0)
    sample_count = models.IntegerField("依据样本数", default=0)
    top_features = models.JSONField("主要影响特征", default=list, blank=True)
    baseline_hours = models.FloatField("朴素基线（全局平均）", default=0)
    model_version = models.CharField("模型版本", max_length=32, default="wma-v1")

    class Meta:
        verbose_name = "审批时效预测"
        verbose_name_plural = "审批时效预测"


class UrgeRecord(models.Model):
    """催办记录（分级智能催办，可追溯）。"""

    created_at = models.DateTimeField("时间", default=timezone.now, db_index=True)
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name="urges")
    task = models.ForeignKey(ApprovalTask, null=True, blank=True, on_delete=models.SET_NULL)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_urges")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_urges")
    cc_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="cc_urges")
    level = models.CharField("催办级别", max_length=8, default="normal",
                             choices=[("normal", "普通"), ("medium", "中风险提醒"), ("high", "高风险抄送上级")])
    channel = models.CharField("渠道", max_length=16, default="site")
    content = models.CharField("内容", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "催办记录"
        verbose_name_plural = "催办记录"
        ordering = ["-id"]


class WorkflowReplayRun(models.Model):
    """流程沙盘回放任务（创新点 6.2）。"""

    class Status(models.TextChoices):
        PENDING = "pending", "排队中"
        RUNNING = "running", "执行中"
        SUCCESS = "success", "已完成"
        FAILED = "failed", "失败"

    created_at = models.DateTimeField("创建时间", default=timezone.now, db_index=True)
    template = models.ForeignKey(WorkflowTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    template_version = models.IntegerField("目标模板版本", default=0)
    since_days = models.IntegerField("回放历史区间（天）", default=90)
    limit = models.IntegerField("单据上限", default=500)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    progress = models.IntegerField("进度", default=0)
    result = models.JSONField("回放报告", default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cost_ms = models.IntegerField("耗时ms", default=0)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "流程沙盘回放"
        verbose_name_plural = "流程沙盘回放"
        ordering = ["-id"]


# ---------------------------------------------------------------- 8 类业务单据
class LeaveRequest(BaseRequest):
    class LeaveType(models.TextChoices):
        ANNUAL = "annual", "年假"
        SICK = "sick", "病假"
        PERSONAL = "personal", "事假"
        MATERNITY = "maternity", "产假"
        OTHER = "other", "其他"

    leave_type = models.CharField("请假类型", max_length=16, choices=LeaveType.choices, default=LeaveType.ANNUAL)
    start_at = models.DateTimeField("开始时间", null=True, blank=True)
    end_at = models.DateTimeField("结束时间", null=True, blank=True)
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "请假申请"
        verbose_name_plural = "请假申请"


class OvertimeRequest(BaseRequest):
    start_at = models.DateTimeField("加班开始", null=True, blank=True)
    end_at = models.DateTimeField("加班结束", null=True, blank=True)
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "加班申请"
        verbose_name_plural = "加班申请"


class TripRequest(BaseRequest):
    destination = models.CharField("目的地", max_length=128, blank=True, default="")
    start_at = models.DateTimeField("出发时间", null=True, blank=True)
    end_at = models.DateTimeField("返回时间", null=True, blank=True)
    budget = models.DecimalField("预算", max_digits=14, decimal_places=2, null=True, blank=True)
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "出差申请"
        verbose_name_plural = "出差申请"


class CardReissueRequest(BaseRequest):
    miss_date = models.DateField("缺卡日期", null=True, blank=True)
    miss_type = models.CharField("缺卡类型", max_length=16, default="sign_in",
                                 choices=[("sign_in", "上班卡"), ("sign_out", "下班卡")])
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "补卡申请"
        verbose_name_plural = "补卡申请"


class PurchaseRequest(BaseRequest):
    item_name = models.CharField("采购物品", max_length=128, blank=True, default="")
    quantity = models.IntegerField("数量", default=1)
    budget = models.DecimalField("预算", max_digits=14, decimal_places=2, null=True, blank=True)
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "采购申请"
        verbose_name_plural = "采购申请"


class SealRequest(BaseRequest):
    class SealType(models.TextChoices):
        COMPANY = "company", "公章"
        CONTRACT = "contract", "合同章"
        FINANCE = "finance", "财务章"
        LEGAL = "legal", "法人章"

    seal_type = models.CharField("印章类型", max_length=16, choices=SealType.choices, default=SealType.COMPANY)
    use_count = models.IntegerField("用印份数", default=1)
    reason = models.TextField("事由", blank=True, default="")

    class Meta:
        verbose_name = "用印申请"
        verbose_name_plural = "用印申请"


class ContractRequest(BaseRequest):
    party = models.CharField("对方主体", max_length=128, blank=True, default="")
    contract_name = models.CharField("合同名称", max_length=255, blank=True, default="")
    sign_at = models.DateField("签订日期", null=True, blank=True)
    reason = models.TextField("说明", blank=True, default="")

    class Meta:
        verbose_name = "合同申请"
        verbose_name_plural = "合同申请"


class ExpenseRequest(BaseRequest):
    """费用报销单（接入审批流引擎，审批完成后回写状态）。"""

    class FeeType(models.TextChoices):
        TRAFFIC = "traffic", "交通费"
        TRAVEL = "travel", "差旅费"
        MEAL = "meal", "餐饮费"
        OFFICE = "office", "办公用品"
        ENTERTAIN = "entertain", "招待费"
        OTHER = "other", "其他"

    class PayStatus(models.TextChoices):
        UNPAID = "unpaid", "未支付"
        PAYING = "paying", "支付中"
        PAID = "paid", "已支付"
        REJECTED = "rejected", "支付驳回"

    fee_type = models.CharField("费用类型", max_length=16, choices=FeeType.choices, default=FeeType.OTHER)
    items = models.JSONField("费用明细", default=list, blank=True,
                            help_text="[{name, amount, note, occurred_at}]")
    invoice_count = models.IntegerField("票据张数", default=0)
    remark = models.TextField("备注", blank=True, default="")
    pay_status = models.CharField("支付状态", max_length=16, choices=PayStatus.choices, default=PayStatus.UNPAID)
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="paid_expenses")

    class Meta:
        verbose_name = "费用报销"
        verbose_name_plural = "费用报销"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} {self.title}"

    @property
    def total_amount(self):
        if self.amount is not None:
            return self.amount
        return sum(float(i.get("amount") or 0) for i in (self.items or []))


# ------------------------------------------------------------------ 回写信号
# 任意 BaseRequest 子类（如 ExpenseRequest）与 WorkflowInstance 通过 OneToOne 关联；
# 流程实例状态/当前节点变化时，自动同步到业务单据，保证「审批完成回写」。
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=WorkflowInstance)
def _sync_business_request(sender, instance, **kwargs):
    for rel in WorkflowInstance._meta.related_objects:
        if not rel.one_to_one or rel.related_model is None:
            continue
        if not issubclass(rel.related_model, BaseRequest):
            continue
        try:
            biz = getattr(instance, rel.name, None)
        except Exception:
            biz = None
        if biz is None:
            continue
        changed = False
        if biz.status != instance.status:
            biz.status = instance.status
            changed = True
        node = instance.current_node_name or ""
        if biz.current_node != node:
            biz.current_node = node
            changed = True
        if instance.finished_at and not biz.finished_at:
            biz.finished_at = instance.finished_at
            changed = True
        if changed:
            fields = [f for f in ("status", "current_node", "finished_at") if hasattr(biz, f)]
            biz.save(update_fields=fields)
