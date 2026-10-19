"""初始化 8 类审批流程模板（幂等）。

    python manage.py init_workflow
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.workflow.models import FlowNode, WorkflowTemplate
from apps.workflow.services import publish_template

# category, code, name, 表单定义, 节点列表
TEMPLATES = [
    (
        "leave", "请假申请", [
            {"key": "leave_type", "label": "请假类型", "type": "select", "options": ["年假", "病假", "事假", "产假", "其他"], "required": True},
            {"key": "start_at", "label": "开始时间", "type": "datetime", "required": True},
            {"key": "end_at", "label": "结束时间", "type": "datetime", "required": True},
            {"key": "days", "label": "请假天数", "type": "number", "required": True},
            {"key": "reason", "label": "事由", "type": "textarea", "required": True},
            {"key": "attachment", "label": "附件", "type": "file"},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "approve_mode": "ANY", "sla_hours": 24},
            {"name": "超过3天需部门负责人", "order": 2, "node_type": "condition", "condition_expr": "days > 3"},
            {"name": "部门负责人审批", "order": 3, "approver_source": "DEPT_HEAD", "approve_mode": "ANY", "sla_hours": 24},
            {"name": "HR复核", "order": 4, "approver_source": "HR", "approve_mode": "ANY", "sla_hours": 48},
            {"name": "结束", "order": 5, "node_type": "end"},
        ],
    ),
    (
        "overtime", "加班申请", [
            {"key": "start_at", "label": "加班开始", "type": "datetime", "required": True},
            {"key": "end_at", "label": "加班结束", "type": "datetime", "required": True},
            {"key": "days", "label": "加班时长(小时)", "type": "number", "required": True},
            {"key": "reason", "label": "事由", "type": "textarea", "required": True},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 24},
            {"name": "HR复核", "order": 2, "approver_source": "HR", "sla_hours": 48},
            {"name": "结束", "order": 3, "node_type": "end"},
        ],
    ),
    (
        "trip", "出差申请", [
            {"key": "destination", "label": "目的地", "type": "text", "required": True},
            {"key": "start_at", "label": "出发时间", "type": "datetime", "required": True},
            {"key": "end_at", "label": "返回时间", "type": "datetime", "required": True},
            {"key": "days", "label": "出差天数", "type": "number", "required": True},
            {"key": "budget", "label": "预算金额", "type": "money", "required": True},
            {"key": "reason", "label": "事由", "type": "textarea", "required": True},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 24},
            {"name": "超过5000需财务审批", "order": 2, "node_type": "condition", "condition_expr": "budget > 5000"},
            {"name": "财务审批", "order": 3, "approver_source": "FINANCE", "sla_hours": 48},
            {"name": "结束", "order": 4, "node_type": "end"},
        ],
    ),
    (
        "card", "补卡申请", [
            {"key": "miss_date", "label": "缺卡日期", "type": "date", "required": True},
            {"key": "miss_type", "label": "缺卡类型", "type": "select", "options": ["上班卡", "下班卡"], "required": True},
            {"key": "reason", "label": "事由", "type": "textarea", "required": True},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 12},
            {"name": "HR复核", "order": 2, "approver_source": "HR", "sla_hours": 24},
            {"name": "结束", "order": 3, "node_type": "end"},
        ],
    ),
    (
        "expense", "费用报销", [
            {"key": "amount", "label": "报销金额", "type": "money", "required": True},
            {"key": "fee_type", "label": "费用类型", "type": "select",
             "options": ["交通费", "差旅费", "餐饮费", "办公用品", "招待费", "其他"], "required": True},
            {"key": "invoice_count", "label": "票据张数", "type": "number", "required": True},
            {"key": "reason", "label": "事由", "type": "textarea", "required": True},
            {"key": "attachment", "label": "票据照片", "type": "image"},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 24},
            {"name": "财务审核", "order": 2, "approver_source": "FINANCE", "sla_hours": 48},
            {"name": "超过10000需总监会签", "order": 3, "node_type": "condition", "condition_expr": "amount > 10000"},
            {"name": "总监会签", "order": 4, "approver_source": "ROLE", "approver_role_codes": ["manager"],
             "approve_mode": "ALL", "sla_hours": 48},
            {"name": "结束", "order": 5, "node_type": "end"},
        ],
    ),
    (
        "purchase", "采购申请", [
            {"key": "item_name", "label": "采购物品", "type": "text", "required": True},
            {"key": "quantity", "label": "数量", "type": "number", "required": True},
            {"key": "budget", "label": "预算金额", "type": "money", "required": True},
            {"key": "reason", "label": "用途说明", "type": "textarea", "required": True},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 24},
            {"name": "财务审核", "order": 2, "approver_source": "FINANCE", "sla_hours": 48},
            {"name": "行政复核", "order": 3, "approver_source": "ROLE", "approver_role_codes": ["admin_staff"], "sla_hours": 24},
            {"name": "结束", "order": 4, "node_type": "end"},
        ],
    ),
    (
        "seal", "用印申请", [
            {"key": "seal_type", "label": "印章类型", "type": "select",
             "options": ["公章", "合同章", "财务章", "法人章"], "required": True},
            {"key": "use_count", "label": "用印份数", "type": "number", "required": True},
            {"key": "reason", "label": "用印事由", "type": "textarea", "required": True},
            {"key": "attachment", "label": "用印文件", "type": "file"},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 12},
            {"name": "行政审核", "order": 2, "approver_source": "ROLE", "approver_role_codes": ["admin_staff"], "sla_hours": 24},
            {"name": "管理员批准", "order": 3, "approver_source": "ADMIN", "sla_hours": 24},
            {"name": "结束", "order": 4, "node_type": "end"},
        ],
    ),
    (
        "contract", "合同审批", [
            {"key": "contract_name", "label": "合同名称", "type": "text", "required": True},
            {"key": "party", "label": "对方主体", "type": "text", "required": True},
            {"key": "amount", "label": "合同金额", "type": "money", "required": True},
            {"key": "sign_at", "label": "签订日期", "type": "date", "required": True},
            {"key": "reason", "label": "说明", "type": "textarea"},
        ], [
            {"name": "直属主管审批", "order": 1, "approver_source": "LEADER", "sla_hours": 24},
            {"name": "财务审核", "order": 2, "approver_source": "FINANCE", "sla_hours": 48},
            {"name": "管理员批准", "order": 3, "approver_source": "ADMIN", "sla_hours": 48},
            {"name": "结束", "order": 4, "node_type": "end"},
        ],
    ),
]


class Command(BaseCommand):
    help = "初始化 8 类审批流程模板并发布"

    @transaction.atomic
    def handle(self, *args, **opts):
        operator = User.objects.filter(is_superuser=True).first()
        created = 0
        for category, name, form_schema, nodes in TEMPLATES:
            tpl, ok_ = WorkflowTemplate.objects.get_or_create(
                code=category, version=1,
                defaults={"name": name, "category": category, "form_schema": form_schema, "sort": 0},
            )
            if ok_:
                created += 1
            if tpl.nodes.filter(is_deleted=False).count() == 0:
                for n in nodes:
                    FlowNode.objects.create(
                        template=tpl, name=n["name"], order=n["order"],
                        node_type=n.get("node_type", "approval"),
                        approver_source=n.get("approver_source", "LEADER"),
                        approver_role_codes=n.get("approver_role_codes", []),
                        approve_mode=n.get("approve_mode", "ANY"),
                        condition_expr=n.get("condition_expr", ""),
                        sla_hours=n.get("sla_hours", 24),
                    )
            if not tpl.is_published:
                publish_template(tpl.id, operator)
        self.stdout.write(self.style.SUCCESS(
            f"init_workflow 完成：模板 {WorkflowTemplate.objects.values('code').distinct().count()} 类，"
            f"版本 {WorkflowTemplate.objects.count()} 个，节点 {FlowNode.objects.count()} 个（新增模板 {created}）"
        ))
