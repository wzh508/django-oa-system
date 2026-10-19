"""流程沙盘回放与流程健康度（创新点 6.2）。

回放采用无副作用执行模式：只读历史数据 + 新模板定义做推演，不写业务表、不发消息。
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.common.exceptions import BusinessException

from .condition import check_condition
from .models import ApprovalRecord, ApprovalTask, WorkflowInstance, WorkflowReplayRun, WorkflowTemplate
from .services import _instance_ctx

logger = logging.getLogger(__name__)


def node_history_stats(days: int = 180) -> dict:
    """按节点名称统计历史平均处理时长、超时率、驳回率（纯 Python 聚合，兼容 MySQL/SQLite）。"""
    since = timezone.now() - timedelta(days=days)
    agg: dict = {}

    def bucket(name):
        if name not in agg:
            agg[name] = {"hours": 0.0, "total": 0, "rejected": 0, "overtime": 0}
        return agg[name]

    qs = ApprovalTask.objects.filter(assigned_at__gte=since)
    for t in qs.only("node_name", "status", "assigned_at", "acted_at", "sla_hours"):
        b = bucket(t.node_name)
        if not t.acted_at:
            continue
        hours = (t.acted_at - t.assigned_at).total_seconds() / 3600
        b["hours"] += hours
        b["total"] += 1
        if t.status == ApprovalTask.Status.REJECTED:
            b["rejected"] += 1
        if hours > (t.sla_hours or 24):
            b["overtime"] += 1

    out = {}
    for name, b in agg.items():
        total = b["total"] or 1
        out[name] = {
            "total": b["total"],
            "avg_hours": round(b["hours"] / total, 2),
            "reject_rate": round(b["rejected"] / total, 4),
            "overtime_rate": round(b["overtime"] / total, 4),
        }
    return out


def _avg_hours_map(days: int = 180) -> dict:
    """节点平均处理时长（小时）。用 Python 计算，兼容 SQLite/MySQL。"""
    since = timezone.now() - timedelta(days=days)
    agg: dict = defaultdict(lambda: [0, 0])
    for t in ApprovalTask.objects.filter(assigned_at__gte=since, acted_at__isnull=False).only(
        "node_name", "assigned_at", "acted_at"
    ):
        if not t.acted_at or not t.assigned_at:
            continue
        hours = (t.acted_at - t.assigned_at).total_seconds() / 3600
        agg[t.node_name][0] += hours
        agg[t.node_name][1] += 1
    return {k: round(v[0] / v[1], 2) if v[1] else 0.0 for k, v in agg.items()}


def run_replay(template_id: int, since_days: int = 90, limit: int = 500, operator=None) -> WorkflowReplayRun:
    """在新模板上重放历史单据，输出预演报告。"""
    tpl = WorkflowTemplate.objects.filter(id=template_id).first()
    if tpl is None:
        raise BusinessException("模板不存在", code=4040, status_code=404)

    run = WorkflowReplayRun.objects.create(
        template=tpl, template_version=tpl.version, since_days=since_days, limit=limit,
        status=WorkflowReplayRun.Status.RUNNING, started_at=timezone.now(),
        operator=operator if operator and operator.is_authenticated else None,
    )
    import time

    t0 = time.time()
    try:
        nodes = sorted(tpl.snapshot().get("nodes", []), key=lambda x: x.get("order", 0))
        avg_map = _avg_hours_map()

        since = timezone.now() - timedelta(days=since_days)
        histories = list(
            WorkflowInstance.objects.filter(
                Q(category=tpl.category) & Q(submitted_at__gte=since) & Q(status__in=["approved", "rejected"])
            ).order_by("-submitted_at")[:limit]
        )

        total_hours = 0.0
        node_hits: dict = defaultdict(int)
        node_hours: dict = defaultdict(float)
        node_pending: dict = defaultdict(int)
        countersign = 0
        rejected = 0
        per_case = []

        for inst in histories:
            ctx = _instance_ctx(inst)
            case_hours = 0.0
            idx = 0
            visited = []
            while idx < len(nodes):
                node = nodes[idx]
                ntype = node.get("node_type", "approval")
                if ntype == "end":
                    break
                if ntype == "condition":
                    if not check_condition(node.get("condition_expr", ""), ctx):
                        idx += 2
                    else:
                        idx += 1
                    continue
                name = node.get("name", "")
                h = avg_map.get(name, 0.0) or 8.0  # 无历史样本时用保守默认 8 小时
                case_hours += h
                node_hits[name] += 1
                node_hours[name] += h
                if h > (node.get("sla_hours") or 24):
                    node_pending[name] += 1
                if node.get("approve_mode") == "ALL":
                    countersign += 1
                visited.append(name)
                idx += 1

            # 用历史该单据是否驳回作为经验驳回率的样本权重
            if inst.status == WorkflowInstance.Status.REJECTED:
                rejected += 1
            total_hours += case_hours
            per_case.append({"code": inst.code, "title": inst.title, "hours": round(case_hours, 2),
                             "nodes": visited, "actual_status": inst.status})

        n = max(len(histories), 1)
        node_rows = []
        for name in node_hits:
            node_rows.append({
                "node": name,
                "hit_count": node_hits[name],
                "hit_rate": round(node_hits[name] / n, 4),
                "avg_hours": round(node_hours[name] / node_hits[name], 2),
                "backlog_rate": round(node_pending[name] / node_hits[name], 4),
            })
        node_rows.sort(key=lambda x: (-x["avg_hours"], -x["backlog_rate"]))
        bottlenecks = node_rows[:3]

        run.result = {
            "template": {"id": tpl.id, "code": tpl.code, "name": tpl.name, "version": tpl.version},
            "sample_count": len(histories),
            "since_days": since_days,
            "avg_predict_hours": round(total_hours / n, 2),
            "countersign_rate": round(countersign / n, 4),
            "reject_rate": round(rejected / n, 4),
            "nodes": node_rows,
            "bottleneck_top3": bottlenecks,
            "cases": per_case[:50],
            "advice": _advice(bottlenecks, round(total_hours / n, 2), round(rejected / n, 4)),
        }
        run.status = WorkflowReplayRun.Status.SUCCESS
    except Exception as exc:
        logger.exception("replay failed")
        run.status = WorkflowReplayRun.Status.FAILED
        run.result = {"error": str(exc)}
    finally:
        run.finished_at = timezone.now()
        run.cost_ms = int((time.time() - t0) * 1000)
        run.progress = 100
        run.save()
    return run


def _advice(bottlenecks: list, avg_hours: float, reject_rate: float) -> list:
    advice = []
    if avg_hours > 48:
        advice.append(f"预计平均审批时长 {avg_hours} 小时偏高，建议合并审批层级或提高自动化比例")
    else:
        advice.append(f"预计平均审批时长 {avg_hours} 小时，处于合理区间")
    if reject_rate > 0.2:
        advice.append(f"预计驳回率 {reject_rate:.0%} 偏高，建议在发起页增加填写校验与常见驳回原因提示")
    for b in bottlenecks:
        advice.append(f"瓶颈节点「{b['node']}」平均停留 {b['avg_hours']} 小时、积压率 {b['backlog_rate']:.0%}，"
                      f"建议缩短时限或增设备选审批人")
    return advice


def health_report(days: int = 180) -> dict:
    """流程健康度看板：节点平均停留、超时率、驳回率、瓶颈标记。"""
    stats = node_history_stats(days)
    rows = []
    for name, s in stats.items():
        rows.append({
            "node": name,
            "total": s["total"],
            "avg_hours": s["avg_hours"],
            "overtime_rate": s["overtime_rate"],
            "reject_rate": s["reject_rate"],
            "bottleneck": s["avg_hours"] >= 24 or s["overtime_rate"] >= 0.3,
        })
    rows.sort(key=lambda x: (-x["avg_hours"], -x["overtime_rate"]))

    pending = ApprovalTask.objects.filter(status=ApprovalTask.Status.PENDING)
    now = timezone.now()
    overdue = sum(1 for t in pending if t.due_at and t.due_at < now)
    return {
        "nodes": rows,
        "bottleneck_top3": rows[:3],
        "pending_total": pending.count(),
        "overdue_total": overdue,
        "generated_at": now.isoformat(),
    }
