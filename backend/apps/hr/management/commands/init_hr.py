"""为现有用户补齐员工档案，并生成示例合同 / 培训记录。"""
import random

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.hr.models import Contract, StaffProfile, Training


class Command(BaseCommand):
    help = "为现有用户补齐员工档案，并生成示例合同 / 培训记录"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="先清空后重建")

    def handle(self, *args, **opts):
        if opts["reset"]:
            StaffProfile.objects.all().delete()
            Contract.objects.all().delete()
            Training.objects.all().delete()

        educations = ["本科", "硕士", "大专", "博士"]
        created = 0
        for u in User.objects.filter(is_active=True):
            if StaffProfile.objects.filter(user=u).exists():
                continue
            sp = StaffProfile.objects.create(
                user=u, education=random.choice(educations),
                marital_status="single", native_place="示例市",
                salary=random.randint(8, 30) * 1000,
            )
            created += 1
            Contract.objects.get_or_create(
                employee=u, defaults={"contract_type": "fixed", "status": "active", "salary": sp.salary},
            )
            if random.random() > 0.5:
                Training.objects.create(employee=u, title="新员工入职培训", organization="人力资源部",
                                       hours=8, score="合格")
        self.stdout.write(
            f"员工档案：新增 {created} / 总计 {StaffProfile.objects.count()}；"
            f"合同 {Contract.objects.count()}；培训 {Training.objects.count()}"
        )
