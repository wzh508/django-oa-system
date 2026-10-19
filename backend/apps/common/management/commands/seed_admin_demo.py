"""为演示账号 admin 补齐「可见数据」，并回填 8 类业务单据明细（幂等）。

背景：seed_demo 只生成 WorkflowInstance（流程实例），不写 BaseRequest 明细表，
      且历史待办/消息都分给了部门主管（zhangwei 等），导致用 admin 登录时
      「待办中心」「消息中心」为空，看起来像"库里没数据"。

本命令做四件事：
  1. 以 admin 作为直属上级的员工为发起人，生成在途单据 -> admin 获得待办
  2. 生成 admin 本人发起的单据（走完/部分驳回）-> admin 的「我的申请」有数据
  3. 给 admin 生成未读站内消息
  4. 为历史上没有明细记录的流程实例，回填对应的 8 类单据表

    python manage.py seed_admin_demo
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.message.models import Message
from apps.workflow.models import (
    ApprovalTask,
    CardReissueRequest,
    ContractRequest,
    ExpenseRequest,
    LeaveRequest,
    OvertimeRequest,
    PurchaseRequest,
    SealRequest,
    TripRequest,
    WorkflowInstance,
)
from apps.workflow.services import act_on_task, start_instance

CATS = ["leave", "overtime", "trip", "card", "expense", "purchase", "seal", "contract"]

CAT_NAMES = {
    "leave": "请假申请", "overtime": "加班申请", "trip": "出差申请", "card": "补卡申请",
    "expense": "费用报销", "purchase": "采购申请", "seal": "用印申请", "contract": "合同审批",
}

CAT_MODEL = {
    "leave": LeaveRequest, "overtime": OvertimeRequest, "trip": TripRequest,
    "card": CardReissueRequest, "expense": ExpenseRequest, "purchase": PurchaseRequest,
    "seal": SealRequest, "contract": ContractRequest,
}

LEAVE_TYPES = ["annual", "sick", "personal", "other"]
FEE_TYPES = ["traffic", "travel", "meal", "office", "entertain", "other"]
SEAL_TYPES = ["company", "contract", "finance", "legal"]
ITEMS = ["笔记本电脑", "办公桌椅", "打印机硒鼓", "空调", "投影仪", "文件柜", "考勤机"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "西安", "武汉"]
PARTIES = ["北京云智科技有限公司", "上海数联信息技术有限公司", "深圳市恒信贸易有限公司",
           "杭州锐创软件股份有限公司", "广州立德供应链有限公司"]
REASONS = [
    "客户现场支持，需要当面沟通方案细节",
    "个人事务处理，已与同事做好工作交接",
    "项目上线冲刺阶段，需要连班完成联调",
    "季度采购计划内物资，用于部门日常办公",
    "合同签署需要加盖公章，材料已备齐",
    "行业展会参展，拓展潜在客户资源",
    "系统故障排查，需延长值守时间",
    "新员工入职设备配置需要补充采购",
]


def _rand_dt(now, lo=1, hi=40):
    return now - timedelta(days=random.randint(lo, hi), hours=random.randint(0, 23))


def build_payload(cat, now):
    """按模板定义生成 form_data 与明细字段。"""
    start = _rand_dt(now)
    end = start + timedelta(days=random.randint(0, 4), hours=random.randint(1, 9))
    reason = random.choice(REASONS)
    if cat == "leave":
        return {"leave_type": random.choice(LEAVE_TYPES), "start_at": start.isoformat(),
                "end_at": end.isoformat(), "days": round(random.uniform(0.5, 5), 1),
                "reason": reason}, {"start_at": start, "end_at": end,
                                    "days": round(random.uniform(0.5, 5), 1)}
    if cat == "overtime":
        return {"start_at": start.isoformat(), "end_at": end.isoformat(),
                "days": round(random.uniform(1, 8), 1), "reason": reason}, \
               {"start_at": start, "end_at": end}
    if cat == "trip":
        budget = round(random.uniform(800, 12000), 2)
        return {"destination": random.choice(CITIES), "start_at": start.isoformat(),
                "end_at": end.isoformat(), "days": round(random.uniform(1, 6), 1),
                "budget": budget, "reason": reason}, \
               {"destination": random.choice(CITIES), "start_at": start, "end_at": end,
                "budget": budget, "days": round(random.uniform(1, 6), 1)}
    if cat == "card":
        miss = (now - timedelta(days=random.randint(1, 20))).date()
        return {"miss_date": miss.isoformat(),
                "miss_type": random.choice(["sign_in", "sign_out"]), "reason": reason}, \
               {"miss_date": miss}
    if cat == "expense":
        amount = round(random.uniform(200, 20000), 2)
        items = [{"name": random.choice(["高铁票", "酒店", "餐饮", "打车", "办公用品"]),
                  "amount": str(amount), "note": "", "occurred_at": str(now.date())}]
        return {"amount": amount, "fee_type": random.choice(FEE_TYPES),
                "invoice_count": random.randint(1, 8), "reason": reason}, \
               {"amount": amount, "fee_type": random.choice(FEE_TYPES),
                "invoice_count": random.randint(1, 8), "items": items}
    if cat == "purchase":
        budget = round(random.uniform(500, 30000), 2)
        return {"item_name": random.choice(ITEMS), "quantity": random.randint(1, 20),
                "budget": budget, "reason": reason}, \
               {"item_name": random.choice(ITEMS), "quantity": random.randint(1, 20),
                "budget": budget, "amount": budget}
    if cat == "seal":
        return {"seal_type": random.choice(SEAL_TYPES), "use_count": random.randint(1, 10),
                "reason": reason}, {"seal_type": random.choice(SEAL_TYPES),
                                    "use_count": random.randint(1, 10)}
    # contract
    return {"party": random.choice(PARTIES), "contract_name": f"{random.choice(PARTIES)}采购合同",
            "sign_at": now.date().isoformat(), "reason": reason}, \
           {"party": random.choice(PARTIES), "sign_at": now.date(),
            "amount": round(random.uniform(5000, 200000), 2)}


def make_detail(cat, instance, applicant, payload, code):
    """根据类别创建 BaseRequest 明细并挂到流程实例上。"""
    model = CAT_MODEL[cat]
    base = dict(
        code=code, title=instance.title, applicant=applicant, dept=applicant.dept,
        status=instance.status, current_node=instance.current_node_name or "",
        submitted_at=instance.submitted_at, finished_at=instance.finished_at,
        workflow_instance=instance, form_data=instance.form_data or {},
        amount=instance.amount, days=instance.days, created_by=applicant,
    )
    if cat == "leave":
        return model(leave_type=payload.get("leave_type", "annual"),
                     start_at=payload["start_at"], end_at=payload["end_at"],
                     reason=payload.get("reason", ""), **base)
    if cat == "overtime":
        return model(start_at=payload["start_at"], end_at=payload["end_at"],
                     reason=payload.get("reason", ""), **base)
    if cat == "trip":
        return model(destination=payload.get("destination", ""), start_at=payload["start_at"],
                     end_at=payload["end_at"], budget=payload.get("budget"),
                     reason=payload.get("reason", ""), **base)
    if cat == "card":
        return model(miss_date=payload["miss_date"],
                     miss_type=payload.get("miss_type", "sign_in"),
                     reason=payload.get("reason", ""), **base)
    if cat == "expense":
        return model(fee_type=payload.get("fee_type", "other"),
                     items=payload.get("items", []),
                     invoice_count=payload.get("invoice_count", 0),
                     remark=payload.get("reason", ""), **base)
    if cat == "purchase":
        return model(item_name=payload.get("item_name", ""),
                     quantity=payload.get("quantity", 1),
                     budget=payload.get("budget"), reason=payload.get("reason", ""), **base)
    if cat == "seal":
        return model(seal_type=payload.get("seal_type", "company"),
                     use_count=payload.get("use_count", 1),
                     reason=payload.get("reason", ""), **base)
    return model(party=payload.get("party", ""), contract_name=payload.get("contract_name", ""),
                 sign_at=payload.get("sign_at"), reason=payload.get("reason", ""), **base)


class Command(BaseCommand):
    help = "为 admin 补齐待办/消息/本人申请，并回填 8 类单据明细（幂等）"

    def add_arguments(self, parser):
        parser.add_argument("--todos", type=int, default=8, help="为 admin 生成的在途待办数量")
        parser.add_argument("--own", type=int, default=6, help="为 admin 生成的本人申请数量")
        parser.add_argument("--messages", type=int, default=12, help="为 admin 生成的未读消息数量")

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(20260922)
        admin = User.objects.filter(username="admin", is_superuser=True).first()
        if admin is None:
            self.stderr.write(self.style.ERROR("未找到 admin 超级管理员，请先执行 init_base"))
            return
        now = timezone.now()

        n_todo = self._make_todos(admin, opts["todos"], now)
        n_own = self._make_own(admin, opts["own"], now)
        n_msg = self._make_messages(admin, opts["messages"], now)
        n_fill = self._backfill_details(admin, now)

        self.stdout.write(self.style.SUCCESS(
            "seed_admin_demo 完成：新增待办 %d / 本人申请 %d / 未读消息 %d / 回填单据明细 %d"
            % (n_todo, n_own, n_msg, n_fill)
        ))
        self.stdout.write(
            "  当前 admin 待办 %d 条，未读消息 %d 条，全库流程实例 %d 个"
            % (ApprovalTask.objects.filter(assignee=admin, status=ApprovalTask.Status.PENDING).count(),
               Message.objects.filter(recipient=admin, is_read=False).count(),
               WorkflowInstance.objects.count())
        )

    # ------------------------------------------------------------------ 待办
    def _make_todos(self, admin, count, now):
        """发起人取「直属上级是 admin」的员工，首个节点 LEADER 即解析为 admin。"""
        applicants = [u for u in User.objects.filter(is_active=True, dept__isnull=False)
                      if u.dept.leader_id == admin.id and u.id != admin.id]
        if not applicants:
            self.stdout.write(self.style.WARNING("没有以 admin 为直属上级的员工，跳过待办生成"))
            return 0
        have = ApprovalTask.objects.filter(assignee=admin, status=ApprovalTask.Status.PENDING).count()
        need = max(0, count - have)
        if need == 0:
            return 0
        created = 0
        for i in range(need):
            cat = CATS[i % len(CATS)]
            applicant = applicants[i % len(applicants)]
            payload, meta = build_payload(cat, now)
            title = "%s-%s" % (CAT_NAMES[cat], applicant.display_name or applicant.username)
            try:
                wf = start_instance(
                    applicant=applicant, template_code=cat, title=title,
                    form_data=payload, category=cat,
                    amount=meta.get("amount"), days=meta.get("days"),
                    urgency=random.choice(["low", "normal", "normal", "high"]),
                )
            except Exception as exc:  # 模板缺失等异常不阻断整体
                self.stderr.write("  [跳过] %s: %s" % (cat, exc))
                continue
            detail_code = "DEMO%s%05d" % (cat[:4].upper(), wf.id)
            try:
                detail = make_detail(cat, wf, applicant, payload, detail_code)
                detail.save()
            except Exception as exc:
                self.stderr.write("  [明细跳过] %s: %s" % (cat, exc))
            created += 1
        return created

    # ------------------------------------------------------------ admin 本人申请
    def _make_own(self, admin, count, now):
        existing = WorkflowInstance.objects.filter(applicant=admin).count()
        need = max(0, count - existing)
        if need == 0:
            return 0
        created = 0
        for i in range(need):
            cat = CATS[i % len(CATS)]
            payload, meta = build_payload(cat, now)
            title = "%s（本人）" % CAT_NAMES[cat]
            try:
                wf = start_instance(
                    applicant=admin, template_code=cat, title=title,
                    form_data=payload, category=cat,
                    amount=meta.get("amount"), days=meta.get("days"),
                    urgency="normal",
                )
            except Exception as exc:
                self.stderr.write("  [跳过] %s: %s" % (cat, exc))
                continue
            detail_code = "SELF%s%05d" % (cat[:4].upper(), wf.id)
            try:
                make_detail(cat, wf, admin, payload, detail_code).save()
            except Exception as exc:
                self.stderr.write("  [明细跳过] %s: %s" % (cat, exc))
            # 走完流程：偶数单通过，第 3 单驳回，其余保留在途
            if i % 3 == 2:
                self._finish(wf, reject=True)
            elif i % 3 == 0:
                self._finish(wf, reject=False)
            created += 1
        return created

    def _finish(self, wf, reject=False):
        for _ in range(12):
            task = ApprovalTask.objects.filter(instance=wf, status=ApprovalTask.Status.PENDING).first()
            if task is None:
                break
            act_on_task(task.id, task.assignee, "reject" if reject else "approve",
                        "材料需补正" if reject else "同意")
            wf.refresh_from_db()
            if wf.status in (wf.Status.APPROVED, wf.Status.REJECTED):
                break

    # ------------------------------------------------------------------ 消息
    def _make_messages(self, admin, count, now):
        have = Message.objects.filter(recipient=admin).count()
        need = max(0, count - have)
        if need == 0:
            return 0
        samples = [
            ("待办提醒", "你有新的审批单据待处理，请及时查看。", "workflow", "warning"),
            ("流程超时预警", "《费用报销》已超过 SLA 时效，请尽快处理。", "workflow", "urgent"),
            ("加签通知", "陈静邀请你参与《采购申请》的审批。", "workflow", "info"),
            ("报销支付完成", "你提交的差旅报销已完成支付，金额 ¥3,200.00。", "expense", "info"),
            ("补卡申请已通过", "你提交的补卡申请已通过 HR 复核。", "workflow", "info"),
            ("公告发布", "《关于 2026 年国庆节放假安排的通知》已发布。", "announcement", "warning"),
            ("会议邀请", "「季度经营分析会」将于明天 10:00 在三楼会议室召开。", "meeting", "info"),
            ("考勤异常提醒", "你 09-18 存在缺卡记录，请及时提交补卡申请。", "attendance", "warning"),
            ("合同到期提醒", "员工劳动合同将于 30 天内到期，请安排续签。", "hr", "warning"),
            ("系统维护通知", "系统将于本周六 02:00-04:00 进行例行维护。", "system", "info"),
            ("任务指派", "你被指派任务：整理 Q3 运营数据报表。", "task", "info"),
            ("流程已驳回", "你提交的《出差申请》被驳回，原因：预算超标。", "workflow", "urgent"),
        ]
        sender = User.objects.filter(username="zhangwei").first()
        created = 0
        for i in range(need):
            title, content, biz, level = samples[i % len(samples)]
            msg = Message.objects.create(
                recipient=admin, sender=sender, title=title, content=content,
                level=level, biz_type=biz, biz_id="", is_read=(i % 5 == 4),
                created_by=sender or admin,
            )
            if msg.is_read:
                msg.read_at = now - timedelta(hours=random.randint(1, 48))
                msg.save(update_fields=["read_at"])
            created += 1
        return created

    # -------------------------------------------------------------- 明细回填
    def _backfill_details(self, admin, now):
        """历史实例（seed_demo 生成）没有明细记录，这里按类别补齐。"""
        total = 0
        for cat in CATS:
            model = CAT_MODEL[cat]
            linked = set(model.objects.values_list("workflow_instance_id", flat=True))
            qs = WorkflowInstance.objects.filter(category=cat).exclude(id__in=[i for i in linked if i])
            for wf in qs.order_by("id"):
                payload, _meta = build_payload(cat, now)
                code = "BF%s%05d" % (cat[:4].upper(), wf.id)
                if model.objects.filter(code=code).exists():
                    continue
                try:
                    make_detail(cat, wf, wf.applicant, payload, code).save()
                    total += 1
                except Exception as exc:
                    self.stderr.write("  [回填跳过] %s#%s: %s" % (cat, wf.id, exc))
        return total
