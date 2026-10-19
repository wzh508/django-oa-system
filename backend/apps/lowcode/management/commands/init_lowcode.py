"""初始化演示低代码表单（幂等）。

    python manage.py init_lowcode
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.lowcode.models import DynamicRecord, FormSchema


class Command(BaseCommand):
    help = "初始化演示低代码表单（满意度调研 / 物品领用）并生成示例数据"

    def handle(self, *args, **opts):
        if FormSchema.objects.filter(code="satisfaction").exists():
            self.stdout.write(self.style.WARNING("低代码演示表单已存在，跳过"))
            return

        satisfaction = FormSchema.objects.create(
            code="satisfaction", name="员工满意度调研", description="季度满意度问卷", category="hr",
            version=1, status=FormSchema.Status.PUBLISHED, created_by=None, fields=[
                {"key": "score", "label": "总体满意度(1-5)", "type": "number", "required": True, "col": 12},
                {"key": "aspect", "label": "最满意方面", "type": "select", "options": ["薪酬", "氛围", "成长", "管理"], "required": True, "col": 12},
                {"key": "suggestion", "label": "改进建议", "type": "textarea", "required": False, "col": 24},
            ],
        )
        supplies = FormSchema.objects.create(
            code="supplies", name="办公用品领用", description="日常办公用品申领", category="admin",
            version=1, status=FormSchema.Status.PUBLISHED, created_by=None, fields=[
                {"key": "item", "label": "物品名称", "type": "text", "required": True, "col": 12},
                {"key": "qty", "label": "数量", "type": "number", "required": True, "col": 6},
                {"key": "reason", "label": "用途", "type": "text", "required": False, "col": 12},
            ],
        )
        # 示例数据
        emp = User.objects.filter(username="liuyang", is_active=True).first()
        if emp:
            DynamicRecord.objects.create(
                form=satisfaction, form_code="satisfaction", submitter=emp,
                form_data={"score": 4, "aspect": "成长", "suggestion": "希望更多培训"},
            )
            DynamicRecord.objects.create(
                form=supplies, form_code="supplies", submitter=emp,
                form_data={"item": "打印纸", "qty": 5, "reason": "部门消耗"},
            )
        self.stdout.write(self.style.SUCCESS(
            f"init_lowcode 完成：表单 {FormSchema.objects.count()} 个，数据 {DynamicRecord.objects.count()} 条"
        ))
