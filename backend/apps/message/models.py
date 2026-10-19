"""站内消息模型。"""
from django.db import models

from apps.common.models import BaseModel


class Message(BaseModel):
    """站内消息（收件箱）。"""

    class Level(models.TextChoices):
        INFO = "info", "普通"
        WARNING = "warning", "提醒"
        URGENT = "urgent", "紧急"

    recipient = models.ForeignKey("accounts.User", verbose_name="接收人", on_delete=models.CASCADE,
                                 related_name="messages", db_index=True)
    sender = models.ForeignKey("accounts.User", verbose_name="发送人", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="sent_messages")
    title = models.CharField("标题", max_length=200)
    content = models.CharField("内容", max_length=1000, blank=True, default="")
    level = models.CharField("级别", max_length=16, choices=Level.choices, default=Level.INFO)
    biz_type = models.CharField("业务类型", max_length=64, blank=True, default="", db_index=True)
    biz_id = models.CharField("业务ID", max_length=64, blank=True, default="")
    is_read = models.BooleanField("已读", default=False, db_index=True)
    read_at = models.DateTimeField("读取时间", null=True, blank=True)

    class Meta:
        verbose_name = "站内消息"
        verbose_name_plural = "站内消息"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"[{self.get_level_display()}] {self.title}"
