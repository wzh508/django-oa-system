"""演示数据生成器（可答辩场景）。

    python manage.py seed_demo [--scale small|medium|large] [--reset]

生成内容：
- 近 3 个月的审批单据（覆盖 8 类单据、全部状态），含审批时长分布
- 特殊场景：会签卡单样本、超时未审批样本、跨部门越权样本
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Department, Position, Role, User, UserRole
from apps.workflow.models import (
    ApprovalRecord,
    ApprovalTask,
    FlowNode,
    WorkflowInstance,
    WorkflowTemplate,
)
from apps.workflow.services import _instance_ctx, resolve_approvers

SCALE = {
    "small": {"users": 10, "instances": 60, "days": 90},
    "medium": {"users": 30, "instances": 200, "days": 90},
    "large": {"users": 60, "instances": 800, "days": 120},
}

CATEGORIES = ["leave", "overtime", "trip", "card", "expense", "purchase", "seal", "contract"]

TITLES = {
    "leave": "请假申请", "overtime": "加班申请", "trip": "出差申请", "card": "补卡申请",
    "expense": "费用报销", "purchase": "采购申请", "seal": "用印申请", "contract": "合同审批",
}


class Command(BaseCommand):
    help = "生成演示数据（组织架构、用户、审批单据、特殊场景样本）"

    def add_arguments(self, parser):
        parser.add_argument("--scale", default="medium", choices=list(SCALE))
        parser.add_argument("--reset", action="store_true", help="清空业务演示数据后重建")
        parser.add_argument("--password", default="Oa@123456")

    @transaction.atomic
    def handle(self, *args, **opts):
        cfg = SCALE[opts["scale"]]
        if opts["reset"]:
            ApprovalTask.objects.all().delete()
            ApprovalRecord.objects.all().delete()
            WorkflowInstance.objects.all().delete()
            self.stdout.write("已清空历史审批数据")

        self._ensure_users(cfg["users"], opts["password"])
        instances = self._gen_instances(cfg["instances"], cfg["days"])
        self._gen_special_cases()
        self.stdout.write(self.style.SUCCESS(
            f"seed_demo 完成：用户 {User.objects.count()} / 流程实例 {WorkflowInstance.objects.count()} "
            f"/ 审批任务 {ApprovalTask.objects.count()} / 审批历史 {ApprovalRecord.objects.count()}（新增 {instances} 单）"
        ))

    # ---------------------------------------------------------------- 用户
    def _ensure_users(self, need: int, password: str) -> None:
        depts = list(Department.objects.filter(is_deleted=False))
        positions = list(Position.objects.filter(is_deleted=False))
        roles = {r.code: r for r in Role.objects.filter(is_deleted=False)}
        if not depts or not positions:
            self.stdout.write(self.style.WARNING("缺少部门/岗位，请先执行 init_base"))
            return

        surnames = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
        names = "伟芳娜秀英敏静丽强磊洋艳勇军杰娟涛明超秀霞平刚桂英建华文博思远子涵"
        base = User.objects.count()
        for i in range(max(0, need - base + 8)):
            idx = base + i
            dept = depts[idx % len(depts)]
            username = f"emp{idx:03d}"
            if User.objects.filter(username=username).exists():
                continue
            user = User.objects.create(
                username=username,
                first_name=random.choice(surnames) + random.choice(names),
                employee_no=f"E{2000 + idx}",
                dept=dept,
                position=positions[idx % len(positions)],
                mobile=f"13{random.randint(100000000, 999999999)}",
                email=f"{username}@example.com",
                status=User.Status.ACTIVE,
                hired_at=timezone.now().date() - timedelta(days=random.randint(100, 1500)),
            )
            user.set_password(password)
            user.save()
            role = roles.get("employee")
            if role:
                UserRole.objects.get_or_create(user=user, role=role, defaults={"is_primary": True})
        # 保证每个部门都有负责人，便于审批链路演示
        for d in depts:
            if d.leader_id is None:
                d.leader = User.objects.filter(dept=d, is_active=True).first()
                d.save(update_fields=["leader"])

    # ---------------------------------------------------------------- 历史单据
    def _gen_instances(self, count: int, days: int) -> int:
        users = list(User.objects.filter(is_active=True).exclude(username="admin"))
        if not users:
            return 0
        templates = {}
        for cat in CATEGORIES:
            tpl = WorkflowTemplate.objects.filter(code=cat, is_active=True).order_by("-version").first()
            if tpl:
                templates[cat] = tpl
        if not templates:
            self.stdout.write(self.style.WARNING("没有已发布模板，请先执行 init_workflow"))
            return 0

        created = 0
        now = timezone.now()
        for i in range(count):
            cat = CATEGORIES[i % len(CATEGORIES)]
            tpl = templates.get(cat)
            if not tpl:
                continue
            applicant = random.choice(users)
            submitted = now - timedelta(days=random.randint(0, days), hours=random.randint(0, 23))
            amount = round(random.uniform(200, 30000), 2) if cat in ("expense", "purchase", "contract", "trip") else None
            days_val = round(random.uniform(1, 7), 1) if cat in ("leave", "trip") else None

            instance = WorkflowInstance.objects.create(
                code=f"WF{submitted.strftime('%Y%m%d')}{i:05d}",
                title=f"{TITLES[cat]}-{i + 1:04d}",
                template=tpl,
                template_version=tpl.version,
                template_snapshot=tpl.snapshot(),
                applicant=applicant,
                dept=applicant.dept,
                status=WorkflowInstance.Status.PENDING,
                category=cat,
                form_data={"days": float(days_val or 0), "amount": float(amount or 0),
                           "reason": "演示数据"},
                amount=amount,
                days=days_val,
                urgency=random.choice(["low", "normal", "normal", "high"]),
                submitted_at=submitted,
                created_by=applicant,
            )
            ApprovalRecord.objects.create(
                instance=instance, node_name="开始", action=ApprovalRecord.Action.SUBMIT,
                operator=applicant, operator_name=applicant.display_name, comment="提交申请",
            )
            self._simulate(instance, submitted, now)
            created += 1
        return created

    def _simulate(self, instance: WorkflowInstance, submitted, now) -> None:
        """按节点顺序推演历史审批结果：约 12% 驳回，节点耗时服从对数分布。"""
        nodes = sorted(instance.snapshot_nodes, key=lambda x: x.get("order", 0))
        ctx = _instance_ctx(instance)
        idx, cursor = 0, submitted
        will_reject = random.random() < 0.12
        reject_at = random.randint(1, max(1, len(nodes) - 2)) if will_reject else -1
        approved_count = 0

        while idx < len(nodes):
            node = nodes[idx]
            ntype = node.get("node_type", "approval")
            if ntype == "end":
                instance.status = WorkflowInstance.Status.APPROVED
                instance.finished_at = cursor
                break
            if ntype == "condition":
                idx += 1 if _cond(node.get("condition_expr", ""), ctx) else 2
                continue

            from apps.workflow.condition import check_condition

            approvers = resolve_approvers(node, instance.applicant)
            seq = node.get("order", idx)
            instance.current_seq = seq
            instance.current_node_name = node.get("name", "")
            approved_count += 1

            if will_reject and approved_count == reject_at:
                for u in approvers:
                    task = ApprovalTask.objects.create(
                        instance=instance, node_id=node.get("id"), node_name=node.get("name"),
                        seq=seq, assignee=u, mode=node.get("approve_mode", "ANY"),
                        status=ApprovalTask.Status.REJECTED, comment="材料不完整，请补充",
                        assigned_at=cursor, acted_at=cursor + timedelta(hours=random.uniform(1, 20)),
                        sla_hours=node.get("sla_hours", 24), created_by=instance.applicant,
                    )
                ApprovalRecord.objects.create(
                    instance=instance, node_name=node.get("name"), action=ApprovalRecord.Action.REJECT,
                    operator=approvers[0], operator_name=approvers[0].display_name,
                    comment="材料不完整，请补充", created_at=cursor,
                )
                instance.status = WorkflowInstance.Status.REJECTED
                instance.finished_at = cursor + timedelta(hours=20)
                break

            # 正常通过；约 18% 的任务超时（用于超时率统计）
            overtime = random.random() < 0.18
            base_h = node.get("sla_hours", 24)
            cost = random.uniform(base_h * 1.1, base_h * 2.5) if overtime else random.uniform(0.5, base_h * 0.6)
            acted = cursor + timedelta(hours=cost)
            if acted > now:
                # 尚未处理：保留为待办（超时样本）
                acted = None
                status = ApprovalTask.Status.PENDING
            else:
                status = ApprovalTask.Status.APPROVED
            for u in approvers:
                ApprovalTask.objects.create(
                    instance=instance, node_id=node.get("id"), node_name=node.get("name"),
                    seq=seq, assignee=u, mode=node.get("approve_mode", "ANY"), status=status,
                    comment="同意" if status == ApprovalTask.Status.APPROVED else "",
                    assigned_at=cursor, acted_at=acted,
                    due_at=cursor + timedelta(hours=base_h),
                    sla_hours=base_h, created_by=instance.applicant,
                )
            if status == ApprovalTask.Status.PENDING:
                instance.status = WorkflowInstance.Status.PENDING
                instance.finished_at = None
                break
            ApprovalRecord.objects.create(
                instance=instance, node_name=node.get("name"), action=ApprovalRecord.Action.APPROVE,
                operator=approvers[0], operator_name=approvers[0].display_name,
                comment="同意", created_at=acted,
            )
            cursor = acted
            idx += 1
        else:
            instance.status = WorkflowInstance.Status.APPROVED
            instance.finished_at = cursor

        if instance.status == WorkflowInstance.Status.APPROVED and not instance.finished_at:
            instance.finished_at = cursor
        instance.submitted_at = submitted
        instance.save()

    # ---------------------------------------------------------------- 特殊场景
    def _gen_special_cases(self) -> None:
        """构造：会签卡单样本、超时未审批样本。"""
        tpl = WorkflowTemplate.objects.filter(code="expense", is_active=True).order_by("-version").first()
        if not tpl:
            return
        makers = list(User.objects.filter(roles__code="manager"))
        applicant = User.objects.filter(username="liuyang").first() or User.objects.exclude(username="admin").first()
        if not applicant:
            return

        # 会签卡单：总监会签节点，其中一人始终未处理
        node = FlowNode.objects.filter(template=tpl, approve_mode="ALL").order_by("order").first()
        if node:
            inst = WorkflowInstance.objects.create(
                code="WFDEMO-COUNTERSIGN", title="【演示】会签卡单样本-大额报销",
                template=tpl, template_version=tpl.version, template_snapshot=tpl.snapshot(),
                applicant=applicant, dept=applicant.dept, status=WorkflowInstance.Status.PENDING,
                category="expense", form_data={"amount": 28000, "fee_type": "招待费", "reason": "演示会签卡单"},
                amount=28000, submitted_at=timezone.now() - timedelta(days=6), created_by=applicant,
            )
            approvers = resolve_approvers(
                {"approver_source": node.approver_source, "approver_role_codes": node.approver_role_codes,
                 "approver_ids": node.approver_ids}, applicant)
            for i, u in enumerate(approvers):
                ApprovalTask.objects.create(
                    instance=inst, node_id=node.id, node_name="总监会签", seq=node.order, assignee=u,
                    mode="ALL", status=ApprovalTask.Status.APPROVED if i == 0 else ApprovalTask.Status.PENDING,
                    assigned_at=timezone.now() - timedelta(days=5),
                    acted_at=(timezone.now() - timedelta(days=4)) if i == 0 else None,
                    due_at=timezone.now() - timedelta(days=3), sla_hours=48, comment="同意" if i == 0 else "",
                    created_by=applicant,
                )
            inst.current_node_name = "总监会签"
            inst.save()

        # 超时未审批：审批人一直未处理，已超 SLA
        pending_applicant = User.objects.exclude(username="admin").order_by("?").first()
        node2 = FlowNode.objects.filter(template=tpl, node_type="approval").order_by("order").first()
        if node2 and pending_applicant:
            inst2 = WorkflowInstance.objects.create(
                code="WFDEMO-OVERTIME", title="【演示】超时未审批样本",
                template=tpl, template_version=tpl.version, template_snapshot=tpl.snapshot(),
                applicant=pending_applicant, dept=pending_applicant.dept, status=WorkflowInstance.Status.PENDING,
                category="expense", form_data={"amount": 3600, "fee_type": "差旅费", "reason": "演示超时未审批"},
                amount=3600, submitted_at=timezone.now() - timedelta(days=5), created_by=pending_applicant,
            )
            for u in resolve_approvers(
                    {"approver_source": node2.approver_source, "approver_role_codes": node2.approver_role_codes,
                     "approver_ids": node2.approver_ids}, pending_applicant):
                ApprovalTask.objects.create(
                    instance=inst2, node_id=node2.id, node_name=node2.name, seq=node2.order, assignee=u,
                    status=ApprovalTask.Status.PENDING, assigned_at=timezone.now() - timedelta(days=5),
                    due_at=timezone.now() - timedelta(days=3), sla_hours=24, created_by=pending_applicant,
                )
            inst2.current_node_name = node2.name
            inst2.save()
        self.stdout.write("  特殊场景样本：会签卡单 1 单、超时未审批 1 单")


def _cond(expr: str, ctx: dict) -> bool:
    from apps.workflow.condition import check_condition

    return check_condition(expr, ctx)
