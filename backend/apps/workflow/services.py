"""审批流引擎（services 层）。

view 只做参数校验与响应组装，所有流程推进逻辑集中在此。
引擎推进使用数据库事务 + 行锁，防止并发重复审批。
"""
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User, UserRole
from apps.common.exceptions import BusinessException, ConflictException, PermissionDeniedException
from apps.common.notify import notify_users

from .condition import check_condition
from .models import (
    ApprovalRecord,
    ApprovalTask,
    FlowNode,
    UrgeRecord,
    WorkflowInstance,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ 状态机
ALLOWED_TRANSITIONS = {
    WorkflowInstance.Status.DRAFT: {WorkflowInstance.Status.PENDING, WorkflowInstance.Status.REVOKED},
    WorkflowInstance.Status.PENDING: {
        WorkflowInstance.Status.APPROVED,
        WorkflowInstance.Status.REJECTED,
        WorkflowInstance.Status.REVOKED,
        WorkflowInstance.Status.TERMINATED,
    },
    WorkflowInstance.Status.APPROVED: set(),
    WorkflowInstance.Status.REJECTED: set(),
    WorkflowInstance.Status.REVOKED: {WorkflowInstance.Status.PENDING},
    WorkflowInstance.Status.TERMINATED: set(),
}


def assert_transition(instance: WorkflowInstance, target: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(instance.status, set())
    if target not in allowed:
        raise ConflictException(
            f"非法状态迁移：{instance.get_status_display()} → {dict(WorkflowInstance.Status.choices).get(target, target)}"
        )


# ------------------------------------------------------------------ 审批人解析
def resolve_approvers(node: dict, applicant: User) -> list:
    """按节点配置的审批人来源解析出具体用户。"""
    source = node.get("approver_source", "LEADER")
    users: list = []

    if source == "USER":
        ids = node.get("approver_ids") or []
        users = list(User.objects.filter(id__in=ids, is_active=True))
    elif source == "ROLE":
        codes = node.get("approver_role_codes") or []
        if codes:
            role_ids = Role.objects.filter(code__in=codes).values_list("id", flat=True)
            user_ids = UserRole.objects.filter(role_id__in=role_ids).values_list("user_id", flat=True)
            users = list(User.objects.filter(id__in=user_ids, is_active=True))
    elif source == "LEADER":
        # 发起人直属上级：优先部门负责人，其次上级部门的负责人
        dept = getattr(applicant, "dept", None)
        while dept is not None:
            if dept.leader_id and dept.leader_id != applicant.id:
                users = [dept.leader]
                break
            dept = dept.parent
    elif source == "DEPT_HEAD":
        dept = getattr(applicant, "dept", None)
        while dept is not None:
            if dept.leader_id and dept.leader_id != applicant.id:
                users = [dept.leader]
                break
            dept = dept.parent
    elif source in ("HR", "FINANCE", "ADMIN"):
        codes = {"HR": ["hr"], "FINANCE": ["finance"], "ADMIN": ["admin"]}[source]
        role_ids = Role.objects.filter(code__in=codes).values_list("id", flat=True)
        user_ids = UserRole.objects.filter(role_id__in=role_ids).values_list("user_id", flat=True)
        users = list(User.objects.filter(id__in=user_ids, is_active=True))

    # 兜底：没有任何审批人时交给系统管理员，避免流程卡死
    if not users:
        admin = User.objects.filter(is_superuser=True, is_active=True).first()
        if admin:
            users = [admin]
    return users


def _instance_ctx(instance: WorkflowInstance) -> dict:
    data = instance.form_data or {}
    return {
        "days": instance.days or data.get("days") or 0,
        "amount": instance.amount or data.get("amount") or 0,
        "urgency": instance.urgency,
        "category": instance.category,
        **{k: v for k, v in data.items() if isinstance(v, (int, float, str))},
    }


# ------------------------------------------------------------------ 业务单据明细
# 表单字段名 -> 明细模型字段名 的别名（前端表单沿用统一 key，个别模型字段名不同）
_REQUEST_FIELD_ALIAS = {"reason": "remark"}
# 由 start_instance 显式写入的公共字段，不再从 form_data 覆盖
_REQUEST_RESERVED = {
    "code", "title", "applicant", "dept", "status", "current_node", "submitted_at",
    "finished_at", "workflow_instance", "form_data", "amount", "days", "created_by",
}


def _request_model(category: str):
    """单据类型 -> 明细模型。新增单据类型时只需在此登记。"""
    from . import models as m

    return {
        "leave": m.LeaveRequest,
        "overtime": m.OvertimeRequest,
        "trip": m.TripRequest,
        "card": m.CardReissueRequest,
        "expense": m.ExpenseRequest,
        "purchase": m.PurchaseRequest,
        "seal": m.SealRequest,
        "contract": m.ContractRequest,
    }.get((category or "").strip().lower())


def _coerce_value(field, value):
    """表单值（多为字符串）转成模型字段可接受的值；无法转换时返回 None。"""
    from django.db import models as dm
    from django.utils.dateparse import parse_date, parse_datetime

    if value is None or value == "":
        return None
    try:
        if isinstance(field, dm.DateTimeField):
            if isinstance(value, datetime):
                dt = value
            else:
                dt = parse_datetime(str(value))
                if dt is None:
                    d = parse_date(str(value))
                    dt = datetime.combine(d, time.min) if d else None
            if dt is not None and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        if isinstance(field, dm.DateField):
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return parse_date(str(value))
        if isinstance(field, dm.DecimalField):
            return Decimal(str(value))
        if isinstance(field, dm.IntegerField):
            return int(float(value))
        if isinstance(field, dm.BooleanField):
            return bool(value)
        return str(value)
    except Exception:
        logger.warning("单据明细字段 %s 的值 %r 无法转换，已跳过", getattr(field, "name", "?"), value)
        return None


def _ensure_request_detail(instance: WorkflowInstance) -> None:
    """为业务单据建立明细记录（与流程实例 1:1）。

    引擎原先只创建实例与审批任务，不回写单据明细表，导致考勤等依赖
    LeaveRequest(status=approved) 的模块看不到新提交的单据（请假不抵扣缺勤、
    加班不计入时长）。此处按实例 category 找到对应明细模型并补齐记录，幂等。

    存在两种建单顺序，必须都兼容：
      1) 流程优先（前端 /workflow/requests/ 提交）——尚无明细，直接补建；
      2) 明细优先（报销单视图、种子命令先建 EXP 单再起流程）——此时已有一条
         未关联的明细，接管它而不是再建一条，否则同一 1:1 外键会被占用两次，
         保存时报唯一约束冲突。
    """
    model = _request_model(instance.category)
    if model is None:
        return
    if model.objects.filter(workflow_instance=instance).exists():
        return

    # ---- 明细优先：接管同一发起人刚建好、尚未关联流程的那条明细 ----
    candidates = model.objects.filter(
        applicant=instance.applicant,
        workflow_instance__isnull=True,
        is_deleted=False,
        created_at__gte=timezone.now() - timedelta(minutes=15),
    )
    title = (instance.title or "").strip()
    if title:
        candidates = candidates.filter(title=instance.title)
    target = None
    for cand in candidates.order_by("-id")[:5]:
        # 金额同为线索；任一侧未填则不作为否决条件
        if (instance.amount is not None and cand.amount is not None
                and str(cand.amount) != str(instance.amount)):
            continue
        target = cand
        break
    if target is not None:
        target.workflow_instance = instance
        target.status = model.Status.PENDING
        target.current_node = instance.current_node_name or ""
        target.submitted_at = instance.submitted_at or timezone.now()
        if instance.form_data:
            target.form_data = instance.form_data
        target.save(update_fields=[
            "workflow_instance", "status", "current_node", "submitted_at",
            "form_data", "updated_at",
        ])
        return

    valid = {f.name for f in model._meta.fields}
    payload = {}
    for key, raw in (instance.form_data or {}).items():
        name = key if key in valid else _REQUEST_FIELD_ALIAS.get(key, "")
        if not name or name in _REQUEST_RESERVED or name not in valid:
            continue
        if payload.get(name) not in (None, ""):
            continue
        val = _coerce_value(model._meta.get_field(name), raw)
        if val is not None:
            payload[name] = val

    model.objects.create(
        code=instance.code,
        title=instance.title,
        applicant=instance.applicant,
        dept=instance.dept,
        status=model.Status.PENDING,
        current_node=instance.current_node_name,
        submitted_at=instance.submitted_at,
        workflow_instance=instance,
        form_data=instance.form_data or {},
        amount=instance.amount,
        days=instance.days,
        created_by=instance.created_by,
        **payload,
    )


def _sync_request_detail(instance: WorkflowInstance) -> None:
    """把流程实例的状态 / 当前节点 / 结束时间同步回单据明细表。"""
    model = _request_model(instance.category)
    if model is None:
        return
    detail = model.objects.filter(workflow_instance=instance).first()
    if detail is None:
        return
    detail.status = instance.status
    detail.current_node = instance.current_node_name or detail.current_node
    if instance.finished_at:
        detail.finished_at = instance.finished_at
    detail.save(update_fields=["status", "current_node", "finished_at", "updated_at"])


# ------------------------------------------------------------------ 发起流程
@transaction.atomic
def start_instance(applicant: User, template_code: str, title: str, form_data: dict,
                   category: str = "", amount=None, days=None, urgency: str = "normal",
                   attachment_ids=None) -> WorkflowInstance:
    """提交单据：创建流程实例（冻结模板快照）并生成首个节点任务。"""
    template = (
        WorkflowTemplate.objects.filter(code=template_code, is_active=True, is_deleted=False)
        .order_by("-version")
        .first()
    )
    if template is None:
        raise BusinessException(f"未找到启用的流程模板：{template_code}", code=4040, status_code=404)

    snapshot = template.snapshot()
    nodes = snapshot.get("nodes", [])
    if not nodes:
        raise BusinessException("流程模板未配置节点，无法发起", code=4002)

    code = _gen_instance_code()
    instance = WorkflowInstance.objects.create(
        code=code,
        title=title,
        template=template,
        template_version=template.version,
        template_snapshot=snapshot,
        applicant=applicant,
        dept=applicant.dept,
        status=WorkflowInstance.Status.DRAFT,
        category=category or template.category,
        form_data=form_data or {},
        amount=amount,
        days=days,
        urgency=urgency,
        attachment_ids=attachment_ids or [],
        created_by=applicant,
    )
    ApprovalRecord.objects.create(
        instance=instance, node_name="开始", action=ApprovalRecord.Action.SUBMIT,
        operator=applicant, operator_name=applicant.display_name,
        comment="提交申请", snapshot={"template_version": template.version},
    )
    assert_transition(instance, WorkflowInstance.Status.PENDING)
    instance.status = WorkflowInstance.Status.PENDING
    instance.submitted_at = timezone.now()
    instance.save(update_fields=["status", "submitted_at"])

    _create_tasks_for_seq(instance, start_seq=0)
    _ensure_request_detail(instance)
    return instance


def _gen_instance_code() -> str:
    from uuid import uuid4

    return f"WF{timezone.now().strftime('%Y%m%d')}{uuid4().hex[:8].upper()}"


def _create_tasks_for_seq(instance: WorkflowInstance, start_seq: int = 0, dry_run: bool = False) -> list:
    """从 start_seq 开始找到第一个需要审批的节点并创建任务。

    返回创建的任务列表；若已到流程末尾则返回空列表。
    """
    ctx = _instance_ctx(instance)
    nodes = sorted(instance.snapshot_nodes, key=lambda x: x.get("order", 0))
    total = len(nodes)
    idx = start_seq

    while idx < total:
        node = nodes[idx]
        ntype = node.get("node_type", "approval")

        if ntype == "end":
            return []

        if ntype == "condition":
            if not check_condition(node.get("condition_expr", ""), ctx):
                idx += 2  # 条件不成立：跳过紧随其后的审批节点
            else:
                idx += 1
            continue

        if ntype == "approval":
            instance.current_seq = idx
            instance.current_node_id = node.get("id")
            instance.current_node_name = node.get("name", "")
            if not dry_run:
                instance.save(update_fields=["current_seq", "current_node_id", "current_node_name"])

            approvers = resolve_approvers(node, instance.applicant)
            created = []
            due = timezone.now() + timedelta(hours=node.get("sla_hours", 24) or 24)
            for u in approvers:
                if dry_run:
                    created.append({"assignee": u, "node": node})
                    continue
                task = ApprovalTask.objects.create(
                    instance=instance,
                    node_id=node.get("id"),
                    node_name=node.get("name", ""),
                    seq=idx,
                    assignee=u,
                    mode=node.get("approve_mode", "ANY"),
                    due_at=due,
                    sla_hours=node.get("sla_hours", 24) or 24,
                    created_by=instance.applicant,
                )
                created.append(task)
            if not dry_run:
                notify_users(approvers, "新的待审批单据", f"{instance.applicant.display_name} 提交了《{instance.title}》",
                             biz_type="workflow", biz_id=instance.id)
            return created

        idx += 1
    return []


def _finish_instance(instance: WorkflowInstance, status: str, operator: User, comment: str, action: str) -> None:
    assert_transition(instance, status)
    instance.status = status
    instance.finished_at = timezone.now()
    instance.current_node_name = "结束"
    instance.save(update_fields=["status", "finished_at", "current_node_name"])
    ApprovalRecord.objects.create(
        instance=instance, node_name="结束", action=action, operator=operator,
        operator_name=getattr(operator, "display_name", ""), comment=comment,
        snapshot={"status": status},
    )
    notify_users([instance.applicant], "审批结果通知",
                 f"《{instance.title}》{instance.get_status_display()}", biz_type="workflow", biz_id=instance.id)
    _sync_request_detail(instance)


# ------------------------------------------------------------------ 审批动作
@transaction.atomic
def act_on_task(task_id: int, user: User, action: str, comment: str = "",
                transfer_to: int | None = None, add_user_ids: list | None = None) -> dict:
    """审批动作：同意 / 驳回 / 转办 / 加签 / 退回。"""
    task = (
        ApprovalTask.objects.select_for_update()
        .select_related("instance", "instance__applicant")
        .filter(id=task_id)
        .first()
    )
    if task is None:
        raise BusinessException("审批任务不存在", code=4040, status_code=404)
    if task.assignee_id != user.id:
        raise PermissionDeniedException("该任务不属于当前用户")
    if task.status != ApprovalTask.Status.PENDING:
        raise ConflictException("该任务已处理，不可重复操作")

    instance = task.instance
    if instance.status != WorkflowInstance.Status.PENDING:
        raise ConflictException("流程已结束，无法继续审批")

    node = instance.node_by_seq(task.seq) or {}
    now = timezone.now()

    if action == "approve":
        task.status = ApprovalTask.Status.APPROVED
        task.comment = comment
        task.acted_at = now
        task.save(update_fields=["status", "comment", "acted_at"])
        ApprovalRecord.objects.create(
            instance=instance, task=task, node_name=task.node_name, action=ApprovalRecord.Action.APPROVE,
            operator=user, operator_name=user.display_name, comment=comment,
            snapshot={"mode": task.mode, "seq": task.seq},
        )
        return _after_approve(instance, task, user, comment)

    if action == "reject":
        task.status = ApprovalTask.Status.REJECTED
        task.comment = comment
        task.acted_at = now
        task.save(update_fields=["status", "comment", "acted_at"])
        ApprovalRecord.objects.create(
            instance=instance, task=task, node_name=task.node_name, action=ApprovalRecord.Action.REJECT,
            operator=user, operator_name=user.display_name, comment=comment,
        )
        _cancel_sibling_tasks(instance, task)
        _finish_instance(instance, WorkflowInstance.Status.REJECTED, user, comment, ApprovalRecord.Action.REJECT)
        return {"result": "rejected", "instance_id": instance.id}

    if action == "transfer":
        if not node.get("allow_transfer", True):
            raise PermissionDeniedException("该节点未开启转办")
        if not transfer_to:
            raise BusinessException("缺少转办目标用户", code=4001)
        target = User.objects.filter(id=transfer_to, is_active=True).first()
        if target is None:
            raise BusinessException("转办目标不存在", code=4040, status_code=404)
        task.status = ApprovalTask.Status.TRANSFERRED
        task.comment = comment
        task.acted_at = now
        task.save(update_fields=["status", "comment", "acted_at"])
        new_task = ApprovalTask.objects.create(
            instance=instance, node_id=task.node_id, node_name=task.node_name, seq=task.seq,
            assignee=target, mode=task.mode, transferred_from=user, due_at=task.due_at,
            sla_hours=task.sla_hours, created_by=user,
        )
        ApprovalRecord.objects.create(
            instance=instance, task=new_task, node_name=task.node_name, action=ApprovalRecord.Action.TRANSFER,
            operator=user, operator_name=user.display_name,
            comment=f"转办给 {target.display_name}｜{comment}", snapshot={"to": target.id},
        )
        notify_users([target], "待办转办通知", f"{user.display_name} 将《{instance.title}》转办给你",
                     biz_type="workflow", biz_id=instance.id)
        return {"result": "transferred", "task_id": new_task.id, "to": target.display_name}

    if action == "add_sign":
        if not node.get("allow_add", True):
            raise PermissionDeniedException("该节点未开启加签")
        if not add_user_ids:
            raise BusinessException("缺少加签用户", code=4001)
        targets = list(User.objects.filter(id__in=add_user_ids, is_active=True))
        if not targets:
            raise BusinessException("加签用户不存在", code=4040, status_code=404)
        for t in targets:
            ApprovalTask.objects.create(
                instance=instance, node_id=task.node_id, node_name=task.node_name + "（加签）",
                seq=task.seq, assignee=t, mode="ALL", is_added=True, added_by=user,
                due_at=now + timedelta(hours=task.sla_hours or 24), sla_hours=task.sla_hours, created_by=user,
            )
        ApprovalRecord.objects.create(
            instance=instance, task=task, node_name=task.node_name, action=ApprovalRecord.Action.ADD_SIGN,
            operator=user, operator_name=user.display_name,
            comment=f"加签：{'、'.join(t.display_name for t in targets)}｜{comment}",
        )
        notify_users(targets, "加签审批通知", f"{user.display_name} 邀请你参与《{instance.title}》审批",
                     biz_type="workflow", biz_id=instance.id)
        return {"result": "added", "count": len(targets)}

    if action == "rollback":
        prev_seq = max(task.seq - 1, 0)
        ApprovalTask.objects.filter(instance=instance, seq=task.seq, status=ApprovalTask.Status.PENDING).update(
            status=ApprovalTask.Status.CANCELLED
        )
        task.status = ApprovalTask.Status.CANCELLED
        task.comment = comment
        task.acted_at = now
        task.save(update_fields=["status", "comment", "acted_at"])
        ApprovalRecord.objects.create(
            instance=instance, task=task, node_name=task.node_name, action=ApprovalRecord.Action.ROLLBACK,
            operator=user, operator_name=user.display_name, comment=comment, snapshot={"to_seq": prev_seq},
        )
        created = _create_tasks_for_seq(instance, start_seq=prev_seq)
        if not created:
            _finish_instance(instance, WorkflowInstance.Status.APPROVED, user, "退回后重新通过",
                             ApprovalRecord.Action.APPROVE)
        return {"result": "rolled_back", "seq": prev_seq}

    raise BusinessException(f"不支持的审批动作：{action}", code=4001)


def _cancel_sibling_tasks(instance: WorkflowInstance, current: ApprovalTask) -> None:
    ApprovalTask.objects.filter(
        instance=instance, seq=current.seq, status=ApprovalTask.Status.PENDING
    ).exclude(id=current.id).update(status=ApprovalTask.Status.CANCELLED)


def _after_approve(instance: WorkflowInstance, task: ApprovalTask, user: User, comment: str) -> dict:
    """同意后推进：或签直接进下一节点；会签需全部同意。"""
    siblings = ApprovalTask.objects.filter(instance=instance, seq=task.seq)
    pending = siblings.filter(status=ApprovalTask.Status.PENDING).exclude(id=task.id)

    if task.mode == "ALL" and pending.exists():
        return {"result": "waiting_countersign", "pending": pending.count()}

    _cancel_sibling_tasks(instance, task)

    created = _create_tasks_for_seq(instance, start_seq=task.seq + 1)
    if created:
        instance.current_node_name = created[0].node_name if hasattr(created[0], "node_name") else ""
        _sync_request_detail(instance)
        return {"result": "advanced", "next_node": instance.current_node_name}

    _finish_instance(instance, WorkflowInstance.Status.APPROVED, user, comment, ApprovalRecord.Action.APPROVE)
    return {"result": "approved", "instance_id": instance.id}


# ------------------------------------------------------------------ 撤回 / 催办 / 终止
@transaction.atomic
def revoke_instance(instance_id: int, user: User, comment: str = "") -> dict:
    """撤回：仅发起人可撤回，且当前节点尚未被处理。"""
    instance = WorkflowInstance.objects.select_for_update().filter(id=instance_id).first()
    if instance is None:
        raise BusinessException("流程不存在", code=4040, status_code=404)
    if instance.applicant_id != user.id:
        raise PermissionDeniedException("只有发起人可以撤回")
    if instance.status != WorkflowInstance.Status.PENDING:
        raise ConflictException("仅审批中的单据可撤回")

    first_task = ApprovalTask.objects.filter(instance=instance, seq=instance.current_seq).first()
    if first_task and first_task.status != ApprovalTask.Status.PENDING:
        raise ConflictException("当前节点已处理，无法撤回")

    assert_transition(instance, WorkflowInstance.Status.REVOKED)
    instance.status = WorkflowInstance.Status.REVOKED
    instance.finished_at = timezone.now()
    instance.save(update_fields=["status", "finished_at"])
    ApprovalTask.objects.filter(instance=instance, status=ApprovalTask.Status.PENDING).update(
        status=ApprovalTask.Status.CANCELLED
    )
    ApprovalRecord.objects.create(
        instance=instance, node_name=instance.current_node_name, action=ApprovalRecord.Action.REVOKE,
        operator=user, operator_name=user.display_name, comment=comment,
    )
    _sync_request_detail(instance)
    return {"result": "revoked", "instance_id": instance.id}


def urge_instance(instance_id: int, user: User, comment: str = "") -> dict:
    """催办：发站内信给当前审批人。"""
    instance = WorkflowInstance.objects.filter(id=instance_id).first()
    if instance is None:
        raise BusinessException("流程不存在", code=4040, status_code=404)
    if instance.applicant_id != user.id and not user.is_superuser:
        raise PermissionDeniedException("只有发起人可催办")
    tasks = ApprovalTask.objects.filter(instance=instance, status=ApprovalTask.Status.PENDING)
    if not tasks.exists():
        raise ConflictException("当前没有待审批任务")
    targets = [t.assignee for t in tasks]
    notify_users(targets, "审批催办", f"{user.display_name} 催办《{instance.title}》：{comment}",
                 level="warning", biz_type="workflow", biz_id=instance.id)
    for t in tasks:
        UrgeRecord.objects.create(instance=instance, task=t, from_user=user, to_user=t.assignee,
                                  level="normal", content=comment)
    ApprovalRecord.objects.create(
        instance=instance, node_name=instance.current_node_name, action=ApprovalRecord.Action.URGE,
        operator=user, operator_name=user.display_name, comment=comment,
    )
    return {"result": "urged", "count": len(targets)}


@transaction.atomic
def terminate_instance(instance_id: int, user: User, comment: str = "") -> dict:
    if not user.is_superuser:
        raise PermissionDeniedException("仅系统管理员可终止流程")
    instance = WorkflowInstance.objects.select_for_update().filter(id=instance_id).first()
    if instance is None:
        raise BusinessException("流程不存在", code=4040, status_code=404)
    if instance.status != WorkflowInstance.Status.PENDING:
        raise ConflictException("仅审批中的单据可终止")
    ApprovalTask.objects.filter(instance=instance, status=ApprovalTask.Status.PENDING).update(
        status=ApprovalTask.Status.CANCELLED
    )
    _finish_instance(instance, WorkflowInstance.Status.TERMINATED, user, comment, ApprovalRecord.Action.TERMINATE)
    return {"result": "terminated", "instance_id": instance.id}


# ------------------------------------------------------------------ 模板版本
@transaction.atomic
def publish_template(template_id: int, user: User) -> WorkflowTemplate:
    """发布模板：同一 code 生成新版本，旧版本失效但在途单据不受影响。"""
    tpl = WorkflowTemplate.objects.filter(id=template_id).first()
    if tpl is None:
        raise BusinessException("模板不存在", code=4040, status_code=404)
    nodes = list(FlowNode.objects.filter(template=tpl, is_deleted=False).order_by("order", "id"))
    if not nodes:
        raise BusinessException("模板没有节点，无法发布", code=4002)

    if tpl.is_published:
        new_tpl = WorkflowTemplate.objects.create(
            code=tpl.code, name=tpl.name, category=tpl.category, version=tpl.version + 1,
            description=tpl.description, form_schema=tpl.form_schema, icon=tpl.icon, sort=tpl.sort,
            is_published=True, is_active=True, published_at=timezone.now(), published_by=user, created_by=user,
        )
        for n in nodes:
            FlowNode.objects.create(
                template=new_tpl, name=n.name, order=n.order, node_type=n.node_type,
                approver_source=n.approver_source, approver_ids=n.approver_ids,
                approver_role_codes=n.approver_role_codes, approve_mode=n.approve_mode,
                condition_expr=n.condition_expr, allow_add=n.allow_add, allow_transfer=n.allow_transfer,
                allow_revoke=n.allow_revoke, allow_urge=n.allow_urge, sla_hours=n.sla_hours, created_by=user,
            )
        WorkflowTemplate.objects.filter(code=tpl.code, is_active=True).exclude(id=new_tpl.id).update(is_active=False)
        return new_tpl

    tpl.is_published = True
    tpl.is_active = True
    tpl.published_at = timezone.now()
    tpl.published_by = user
    tpl.save(update_fields=["is_published", "is_active", "published_at", "published_by"])
    return tpl


@transaction.atomic
def rollback_template(template_id: int, user: User) -> WorkflowTemplate:
    """把某个历史版本重新设为生效版本。"""
    tpl = WorkflowTemplate.objects.filter(id=template_id).first()
    if tpl is None:
        raise BusinessException("模板不存在", code=4040, status_code=404)
    WorkflowTemplate.objects.filter(code=tpl.code, is_active=True).exclude(id=tpl.id).update(is_active=False)
    tpl.is_active = True
    tpl.save(update_fields=["is_active"])
    return tpl


def diff_template(a_id: int, b_id: int) -> dict:
    """对比两个模板版本的节点差异。"""
    a = WorkflowTemplate.objects.filter(id=a_id).first()
    b = WorkflowTemplate.objects.filter(id=b_id).first()
    if not a or not b:
        raise BusinessException("模板不存在", code=4040, status_code=404)
    sa = {n.get("order"): n for n in a.snapshot()["nodes"]}
    sb = {n.get("order"): n for n in b.snapshot()["nodes"]}
    keys = ["name", "node_type", "approver_source", "approve_mode", "condition_expr", "sla_hours"]
    changes = []
    for order in sorted(set(sa) | set(sb)):
        na, nb = sa.get(order), sb.get(order)
        if na is None:
            changes.append({"order": order, "type": "added", "name": nb.get("name"), "before": None, "after": nb})
        elif nb is None:
            changes.append({"order": order, "type": "removed", "name": na.get("name"), "before": na, "after": None})
        else:
            diff = {k: {"before": na.get(k), "after": nb.get(k)} for k in keys if na.get(k) != nb.get(k)}
            if diff:
                changes.append({"order": order, "type": "modified", "name": nb.get("name"), "diff": diff})
    return {"left": {"id": a.id, "version": a.version}, "right": {"id": b.id, "version": b.version},
            "changes": changes, "total": len(changes)}
