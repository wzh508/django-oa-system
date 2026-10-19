"""人事域模型：员工档案、入转调离、合同、培训。"""
from django.db import models

from apps.common.models import BaseModel


class StaffProfile(BaseModel):
    """员工档案扩展（敏感信息：薪资 / 证件）。"""

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "未婚"
        MARRIED = "married", "已婚"
        DIVORCED = "divorced", "离异"
        OTHER = "other", "其他"

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="staff_profile",
                                verbose_name="关联账号")
    education = models.CharField("学历", max_length=50, blank=True, default="")
    major = models.CharField("专业", max_length=100, blank=True, default="")
    emergency_contact = models.CharField("紧急联系人", max_length=50, blank=True, default="")
    emergency_phone = models.CharField("紧急联系电话", max_length=30, blank=True, default="")
    marital_status = models.CharField("婚姻状况", max_length=20, choices=MaritalStatus.choices, default=MaritalStatus.SINGLE)
    native_place = models.CharField("籍贯", max_length=100, blank=True, default="")
    probation_end = models.DateField("试用期截止", null=True, blank=True)
    regularized_at = models.DateField("转正日期", null=True, blank=True)
    salary = models.DecimalField("月薪", max_digits=12, decimal_places=2, null=True, blank=True)
    bank_card = models.CharField("工资卡号", max_length=40, blank=True, default="")
    id_card = models.CharField("身份证号", max_length=40, blank=True, default="")

    class Meta:
        db_table = "hr_staff_profile"
        verbose_name = "员工档案"
        verbose_name_plural = "员工档案"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.first_name or self.user.username} 档案"


class Transfer(BaseModel):
    """入转调离记录。"""

    class Type(models.TextChoices):
        ONBOARD = "onboard", "入职"
        REGULAR = "regular", "转正"
        TRANSFER = "transfer", "调岗"
        OFFBOARD = "offboard", "离职"
        REJOIN = "rejoin", "复职"

    class Status(models.TextChoices):
        PENDING = "pending", "待生效"
        DONE = "done", "已生效"
        CANCELLED = "cancelled", "已取消"

    employee = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="transfers", verbose_name="员工")
    type = models.CharField("类型", max_length=20, choices=Type.choices, default=Type.ONBOARD)
    from_dept = models.ForeignKey("accounts.Department", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="transfer_from", verbose_name="原部门")
    to_dept = models.ForeignKey("accounts.Department", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="transfer_to", verbose_name="目标部门")
    from_position = models.ForeignKey("accounts.Position", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="transfer_from_pos", verbose_name="原岗位")
    to_position = models.ForeignKey("accounts.Position", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="transfer_to_pos", verbose_name="目标岗位")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PENDING)
    handler = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="handled_transfers", verbose_name="经办人")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "hr_transfer"
        verbose_name = "入转调离"
        verbose_name_plural = "入转调离"
        ordering = ["-created_at"]


class Contract(BaseModel):
    """劳动合同。"""

    class Type(models.TextChoices):
        FIXED = "fixed", "固定期限"
        NONFIXED = "nonfixed", "无固定期限"
        INTERN = "intern", "实习"
        LABOR = "labor", "劳务"
        PARTTIME = "parttime", "兼职"

    class Status(models.TextChoices):
        ACTIVE = "active", "生效中"
        EXPIRED = "expired", "已到期"
        TERMINATED = "terminated", "已解除"

    employee = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="contracts", verbose_name="员工")
    contract_type = models.CharField("合同类型", max_length=20, choices=Type.choices, default=Type.FIXED)
    sign_date = models.DateField("签订日期", null=True, blank=True)
    start_date = models.DateField("起始日期", null=True, blank=True)
    end_date = models.DateField("终止日期", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    salary = models.DecimalField("合同薪资", max_digits=12, decimal_places=2, null=True, blank=True)
    attachment = models.CharField("附件路径", max_length=500, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "hr_contract"
        verbose_name = "合同"
        verbose_name_plural = "合同"
        ordering = ["-created_at"]


class Training(BaseModel):
    """培训记录。"""

    employee = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="trainings", verbose_name="员工")
    title = models.CharField("培训主题", max_length=200)
    organization = models.CharField("培训机构", max_length=200, blank=True, default="")
    start_date = models.DateField("培训日期", null=True, blank=True)
    hours = models.IntegerField("学时", default=0)
    score = models.CharField("成绩", max_length=50, blank=True, default="")
    certificate = models.CharField("证书", max_length=200, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "hr_training"
        verbose_name = "培训记录"
        verbose_name_plural = "培训记录"
        ordering = ["-created_at"]


# ------------------------------------------------------------------ 建档信号
# 系统不变量：每个账号都有且仅有一条员工档案（StaffProfile.user 是 OneToOne）。
# 以往该不变量靠「先建账号、再手工跑 init_hr」维持，从「用户管理」页新建的账号
# 会静默缺档案：在用户管理里看得到、在人事档案里查不到。
# 这里在账号创建时自动补一条空档案，init_hr 仍作为历史数据的批量补齐工具。
from django.db.models.signals import post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_save, sender="accounts.User")
def _ensure_staff_profile(sender, instance, created, **kwargs):
    """账号创建后立即补一条员工档案，保证「账号 ↔ 档案」1:1 不变量。"""
    if not created:
        return
    if getattr(instance, "is_deleted", False):
        return
    StaffProfile.objects.get_or_create(user=instance)
