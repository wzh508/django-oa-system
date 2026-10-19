"""公告通知域模型。"""
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Announcement(BaseModel):
    """公告 / 通知 / 制度。"""

    class Category(models.TextChoices):
        NOTICE = "notice", "通知"
        ANNOUNCEMENT = "announcement", "公告"
        POLICY = "policy", "制度"

    class Level(models.TextChoices):
        NORMAL = "normal", "普通"
        IMPORTANT = "important", "重要"
        URGENT = "urgent", "紧急"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"

    title = models.CharField("标题", max_length=200)
    content = models.TextField("正文")
    category = models.CharField("类型", max_length=20, choices=Category.choices, default=Category.NOTICE)
    level = models.CharField("级别", max_length=20, choices=Level.choices, default=Level.NORMAL)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    publisher = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                  related_name="announcements", verbose_name="发布人")
    dept = models.ForeignKey("accounts.Department", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="announcements", verbose_name="发布范围(部门)")
    is_top = models.BooleanField("置顶", default=False)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    expire_at = models.DateTimeField("失效时间", null=True, blank=True)
    read_count = models.IntegerField("阅读量", default=0)

    class Meta:
        db_table = "announcement"
        verbose_name = "公告"
        verbose_name_plural = "公告"
        ordering = ["-is_top", "-published_at", "-id"]

    def __str__(self):
        return self.title


class AnnouncementRead(BaseModel):
    """公告阅读记录（用于阅读统计与已读未读）。"""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="announcement_reads")

    class Meta:
        db_table = "announcement_read"
        verbose_name = "阅读记录"
        unique_together = ("announcement", "user")
