"""初始化演示报销数据（幂等）。

    python manage.py init_expense
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from uuid import uuid4

from apps.accounts.models import User
from apps.workflow.models import ApprovalTask, ExpenseRequest
from apps.workflow.services import act_on_task, start_instance


def _create(applicant, title, fee_type, amount, invoice_count, items, remark, urgency="normal"):
    now = timezone.now()
    code = f"EXP{now.strftime('%Y%m%d')}{uuid4().hex[:8].upper()}"
    exp = ExpenseRequest.objects.create(
        applicant=applicant, dept=applicant.dept, code=code, title=title, fee_type=fee_type,
        amount=amount, invoice_count=invoice_count, items=items, remark=remark,
        status=ExpenseRequest.Status.DRAFT, created_by=applicant,
    )
    wf = start_instance(
        applicant=applicant, template_code="expense", title=title,
        form_data={"fee_type": fee_type, "invoice_count": invoice_count, "items": items, "remark": remark},
        category="expense", amount=amount, urgency=urgency, attachment_ids=[],
    )
    exp.workflow_instance = wf
    exp.status = ExpenseRequest.Status.PENDING
    exp.current_node = wf.current_node_name or ""
    exp.submitted_at = wf.submitted_at
    exp.save(update_fields=["workflow_instance", "status", "current_node", "submitted_at"])
    return exp, wf


def _run_chain(wf, reject_first=False):
    rejected = False
    for _ in range(10):
        task = ApprovalTask.objects.filter(instance=wf, status=ApprovalTask.Status.PENDING).first()
        if task is None:
            break
        if reject_first and not rejected:
            act_on_task(task.id, task.assignee, "reject", "材料需补正")
            rejected = True
        else:
            act_on_task(task.id, task.assignee, "approve", "同意")
        wf.refresh_from_db()
        if wf.status in (wf.Status.APPROVED, wf.Status.REJECTED):
            break


class Command(BaseCommand):
    help = "初始化演示报销数据（覆盖审批中/已通过/已支付/已驳回多种状态）"

    def handle(self, *args, **opts):
        if ExpenseRequest.objects.count() >= 8:
            self.stdout.write(self.style.WARNING("报销演示数据已存在，跳过"))
            return
        samples = [
            ("liuyang", "差旅报销-北京客户拜访", "travel", "3200.00", 5,
             [{"name": "高铁票", "amount": "1200.00", "note": "往返", "occurred_at": "2026-09-10"},
              {"name": "酒店", "amount": "2000.00", "note": "2晚", "occurred_at": "2026-09-10"}], "客户拜访差旅", "normal"),
            ("chenjing", "餐饮招待-团队聚餐", "entertain", "880.00", 2,
             [{"name": "聚餐", "amount": "880.00", "note": "项目庆功", "occurred_at": "2026-09-12"}], "团队建设", "normal"),
            ("liuyang", "办公用品采购", "office", "1560.00", 3,
             [{"name": "打印纸", "amount": "360.00", "note": "", "occurred_at": "2026-09-13"},
              {"name": "文具", "amount": "1200.00", "note": "", "occurred_at": "2026-09-13"}], "季度采购", "normal"),
            ("chenjing", "交通费-市内出行", "traffic", "240.00", 4,
             [{"name": "打车", "amount": "240.00", "note": "机场接送", "occurred_at": "2026-09-14"}], "出差交通", "low"),
            ("liuyang", "差旅报销-上海展会", "travel", "6800.00", 8,
             [{"name": "机票", "amount": "3200.00", "note": "往返", "occurred_at": "2026-09-05"},
              {"name": "酒店", "amount": "2800.00", "note": "3晚", "occurred_at": "2026-09-05"},
              {"name": "餐饮", "amount": "800.00", "note": "", "occurred_at": "2026-09-05"}], "行业展会", "high"),
            ("chenjing", "其他费用-培训报名", "other", "1200.00", 1,
             [{"name": "报名费", "amount": "1200.00", "note": "线上课程", "occurred_at": "2026-09-15"}], "技能提升", "normal"),
        ]
        created = 0
        for username, title, fee, amount, inv, items, remark, urgency in samples:
            applicant = User.objects.filter(username=username, is_active=True).first()
            if not applicant:
                continue
            exp, wf = _create(applicant, title, fee, amount, inv, items, remark, urgency)
            created += 1
        # 让前 2 笔走完审批并支付，第 3 笔驳回，其余保持审批中
        pending = list(ExpenseRequest.objects.filter(status=ExpenseRequest.Status.PENDING).order_by("id"))
        if len(pending) >= 3:
            _run_chain(pending[0].workflow_instance)          # 通过
            exp0 = pending[0]
            exp0.refresh_from_db()
            if exp0.status == ExpenseRequest.Status.APPROVED:
                exp0.pay_status = ExpenseRequest.PayStatus.PAID
                exp0.paid_at = timezone.now()
                exp0.paid_by = User.objects.filter(username="wangfang").first()
                exp0.save(update_fields=["pay_status", "paid_at", "paid_by"])
            _run_chain(pending[1].workflow_instance)          # 通过
            _run_chain(pending[2].workflow_instance, reject_first=True)  # 驳回
        self.stdout.write(self.style.SUCCESS(f"init_expense 完成：新建 {created} 条，当前共 {ExpenseRequest.objects.count()} 条"))
