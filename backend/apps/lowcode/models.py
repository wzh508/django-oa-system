"""低代码：动态表单 / 动态数据（创新点 6.5）。

FormSchema 描述一张动态表单的字段定义；DynamicRecord 存储按该 schema 提交的实例数据。
前端依据 schema 实时渲染表单与列表，无需发版即可新增业务采集场景。
"""
from django.db import models

from apps.common.models import BaseModel


class FormSchema(BaseModel):
    """动态表单定义。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"

    code = models.CharField("表单编码", max_length=64, db_index=True)
    name = models.CharField("表单名称", max_length=128)
    description = models.CharField("说明", max_length=255, blank=True, default="")
    category = models.CharField("业务类别", max_length=64, blank=True, default="", db_index=True)
    version = models.IntegerField("版本", default=1)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    fields = models.JSONField("字段定义", default=list, blank=True, help_text=(
        "[{key,label,type,required,options,placeholder,col}]，type∈text/number/select/date/datetime/textarea/file"
    ))

    class Meta:
        verbose_name = "动态表单"
        verbose_name_plural = "动态表单"
        unique_together = ("code", "version")
        ordering = ["code", "-version"]

    def __str__(self):
        return f"{self.name} v{self.version}"


class DynamicRecord(BaseModel):
    """动态表单提交的实例数据。"""

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        DONE = "done", "已处理"
        ARCHIVED = "archived", "已归档"

    form = models.ForeignKey(FormSchema, verbose_name="所属表单", on_delete=models.CASCADE,
                             related_name="records")
    form_code = models.CharField("表单编码", max_length=64, db_index=True)
    form_data = models.JSONField("提交数据", default=dict, blank=True)
    submitter = models.ForeignKey("accounts.User", verbose_name="提交人", on_delete=models.CASCADE,
                                 related_name="dynamic_records")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = "动态数据"
        verbose_name_plural = "动态数据"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["form_code", "status"])]

    def __str__(self):
        return f"{self.form_code} #{self.id}"
