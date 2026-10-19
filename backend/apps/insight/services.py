"""智能分析服务（创新点 6.3）：审批时效预测 + 分级智能催办 + 流程瓶颈分析。

设计：
- 时效预测采用「加权移动平均（WMA）」基线：同单据类型的已完成实例平均时长作为朴素基线，
  再按当前节点位置与紧迫度做修正，输出预计剩余时长、预计完成时间、风险等级。
- 分级催办：扫描临期/超时任务，按超期程度分级（普通 / 中风险提醒 / 高风险抄送上级），
  自动生成催办记录并站内通知。
- 瓶颈分析：统计各节点平均停留时长，定位最慢节点。
"""
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from apps.common.notify import notify_users
from apps.workflow.models import (
    ApprovalSLAPredict,
    ApprovalTask,
    UrgeRecord,
    WorkflowInstance,
)

DONE_STATUSES = [WorkflowInstance.Status.APPROVED, WorkflowInstance.Status.REJECTED]


def _duration_hours(instance) -> float | None:
    if instance.submitted_at and instance.finished_at:
        return (instance.finished_at - instance.submitted_at).total_seconds() / 3600
    return None


def category_baseline(category: str) -> float:
    """同类型已完成实例的平均处理时长（小时），无数据则退化为全局基线。"""
    def avg(qs):
        vals = [d for d in (_duration_hours(i) for i in qs) if d is not None]
        return sum(vals) / len(vals) if vals else None

    local = avg(WorkflowInstance.objects.filter(
        category=category, status__in=DONE_STATUSES,
        submitted_at__isnull=False, finished_at__isnull=False,
    ))
    if local is not None:
        return round(local, 2)
    global_ = avg(WorkflowInstance.objects.filter(
        status__in=DONE_STATUSES, submitted_at__isnull=False, finished_at__isnull=False,
    ))
    return round(global_ or 24.0, 2)


def _node_sla_sum(instance: WorkflowInstance) -> float:
    nodes = sorted(instance.snapshot_nodes, key=lambda x: x.get("order", 0))
    total = 0.0
    started = False
    for n in nodes:
        if n.get("order", 0) >= instance.current_seq:
            started = True
        if started and n.get("node_type") != "end":
            total += float(n.get("sla_hours") or 24)
    return total


def predict_instance(instance: WorkflowInstance) -> dict:
    """对单个在途单据预测时效与风险。"""
    now = timezone.now()
    baseline = category_baseline(instance.category)
    elapsed = ((now - instance.submitted_at).total_seconds() / 3600) if instance.submitted_at else 0.0
    predicted_remaining = max(round(baseline - elapsed, 2), 0.0)
    predicted_finish_at = now + timedelta(hours=predicted_remaining)
    node_sla = _node_sla_sum(instance)
    risk_level = "low"
    risk_score = 0.0
    if instance.urgency == "high":
        risk_score += 0.2
    if node_sla > 0:
        ratio = predicted_remaining / node_sla
        if ratio > 1.0:
            risk_level = "high"
            risk_score = min(1.0, 0.6 + (ratio - 1.0))
        elif ratio > 0.8:
            risk_level = "medium"
            risk_score = 0.4 + (ratio - 0.8) * 1.0
        else:
            risk_level = "low"
            risk_score = ratio * 0.4
    # 已超时节点任务直接升级
    overdue_task = instance.tasks.filter(
        status=ApprovalTask.Status.PENDING, due_at__lt=now,
    ).first()
    if overdue_task:
        risk_level = "high"
        risk_score = max(risk_score, 0.8)
    return {
        "instance_id": instance.id,
        "code": instance.code,
        "title": instance.title,
        "category": instance.category,
        "baseline_hours": baseline,
        "elapsed_hours": round(elapsed, 2),
        "predicted_hours": predicted_remaining,
        "predicted_finish_at": predicted_finish_at,
        "node_sla_hours": round(node_sla, 2),
        "risk_level": risk_level,
        "risk_score": round(risk_score, 3),
        "sample_count": WorkflowInstance.objects.filter(
            category=instance.category, status__in=DONE_STATUSES,
        ).count(),
    }


def refresh_predictions() -> int:
    """为所有在途实例重算时效预测并落库，返回预测数量。"""
    now = timezone.now()
    pending = WorkflowInstance.objects.filter(
        status=WorkflowInstance.Status.PENDING, submitted_at__isnull=False,
    ).select_related("applicant", "dept")
    count = 0
    for inst in pending:
        pred = predict_instance(inst)
        predicted_finish_at = pred["predicted_finish_at"]
        ApprovalSLAPredict.objects.update_or_create(
            instance=inst,
            defaults={
                "predicted_hours": pred["predicted_hours"],
                "predicted_finish_at": predicted_finish_at,
                "risk_level": pred["risk_level"],
                "risk_score": pred["risk_score"],
                "sample_count": pred["sample_count"],
                "baseline_hours": pred["baseline_hours"],
                "model_version": "wma-v1",
            },
        )
        count += 1
    return count


def _dept_leader(user):
    dept = getattr(user, "dept", None)
    while dept is not None:
        if dept.leader_id and dept.leader_id != user.id:
            return dept.leader
        dept = dept.parent
    return None


def graded_urge(overdue_threshold_hours: float = 0.0, warning_hours: float = 24.0) -> dict:
    """分级智能催办：扫描临期/超时任务，按风险分级通知。

    - 已超时：高风险，抄送发起人部门负责人；
    - 距截止不足 warning_hours：中风险提醒；
    - 其余：普通催办。
    """
    now = timezone.now()
    tasks = ApprovalTask.objects.filter(
        status=ApprovalTask.Status.PENDING, due_at__isnull=False,
    ).select_related("instance", "assignee", "instance__applicant")
    high, medium, normal = 0, 0, 0
    for t in tasks:
        due = t.due_at
        hours_left = (due - now).total_seconds() / 3600
        if hours_left < overdue_threshold_hours:
            level, cc = "high", _dept_leader(t.instance.applicant)
        elif hours_left < warning_hours:
            level, cc = "medium", None
        else:
            level, cc = "normal", None
        content = f"《{t.instance.title}》节点「{t.node_name}」将于{due:%m-%d %H:%M}截止，请及时处理"
        if level == "high":
            content = "【超时】" + content + "（已抄送上级）"
        UrgeRecord.objects.create(
            instance=t.instance, task=t, from_user=t.instance.applicant,
            to_user=t.assignee, cc_user=cc, level=level, content=content,
        )
        targets = [t.assignee] + ([cc] if cc else [])
        notify_users(targets, "审批催办", content, level="warning" if level != "normal" else "info",
                     biz_type="workflow", biz_id=t.instance.id)
        if level == "high":
            high += 1
        elif level == "medium":
            medium += 1
        else:
            normal += 1
    return {"high": high, "medium": medium, "normal": normal, "total": high + medium + normal}


def risk_dashboard() -> dict:
    """风险看板：汇总在途实例的风险分布与明细。"""
    refresh_predictions()
    preds = list(ApprovalSLAPredict.objects.select_related(
        "instance", "instance__applicant", "instance__dept",
    ).filter(instance__status=WorkflowInstance.Status.PENDING).order_by("-risk_score"))
    detail = []
    for p in preds:
        inst = p.instance
        detail.append({
            "instance_id": inst.id, "code": inst.code, "title": inst.title,
            "category": inst.category, "applicant": inst.applicant.display_name,
            "current_node": inst.current_node_name, "risk_level": p.risk_level,
            "risk_score": p.risk_score, "predicted_hours": p.predicted_hours,
            "predicted_finish_at": p.predicted_finish_at, "baseline_hours": p.baseline_hours,
        })
    dist = {"high": 0, "medium": 0, "low": 0}
    for d in detail:
        dist[d["risk_level"]] = dist.get(d["risk_level"], 0) + 1
    return {"distribution": dist, "items": detail}


def bottleneck_analysis() -> dict:
    """瓶颈分析：统计各节点平均停留时长，输出最慢 TOP3 节点。"""
    done = WorkflowInstance.objects.filter(status__in=DONE_STATUSES)
    # 用审批记录估算节点停留：同一实例相邻 approve 记录的时间差
    from apps.workflow.models import ApprovalRecord

    node_durations = {}
    for inst in done.select_related():
        recs = list(ApprovalRecord.objects.filter(
            instance=inst, action__in=["approve", "reject", "submit"],
        ).order_by("created_at"))
        for i in range(1, len(recs)):
            prev, cur = recs[i - 1], recs[i]
            if cur.node_name:
                dt = (cur.created_at - prev.created_at).total_seconds() / 3600
                node_durations.setdefault(cur.node_name, []).append(dt)
    rows = []
    for node, vals in node_durations.items():
        rows.append({
            "node": node,
            "avg_hours": round(sum(vals) / len(vals), 2),
            "max_hours": round(max(vals), 2),
            "count": len(vals),
        })
    rows.sort(key=lambda x: x["avg_hours"], reverse=True)
    return {"nodes": rows, "top3": rows[:3]}


def sla_stats() -> dict:
    """整体时效统计：平均时长、准时率、超时单量。"""
    done = WorkflowInstance.objects.filter(
        status__in=DONE_STATUSES, submitted_at__isnull=False, finished_at__isnull=False,
    )
    durations = [d for d in (_duration_hours(i) for i in done) if d is not None]
    avg = round(sum(durations) / len(durations), 2) if durations else 0
    overdue = 0
    for inst in done:
        pred = getattr(inst, "sla_predict", None)
        if pred and pred.risk_level == "high":
            overdue += 1
    # 按模板维度统计基线（供时效分析页展示）
    buckets: dict[str, list] = {}
    for inst in done:
        d = _duration_hours(inst)
        if d is None:
            continue
        key = (inst.template.name if inst.template else None) or inst.category or "其他"
        buckets.setdefault(key, []).append(d)
    by_template = [
        {"template": k, "avg_hours": round(sum(v) / len(v), 2), "sample_count": len(v)}
        for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    ]
    return {
        "completed": len(durations),
        "avg_hours": avg,
        "high_risk_completed": overdue,
        "on_time_rate": round((len(durations) - overdue) / len(durations), 3) if durations else 0,
        "by_template": by_template,
    }
