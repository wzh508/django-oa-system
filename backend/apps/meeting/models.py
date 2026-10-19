"""会议域模型。"""
from django.db import models

from apps.common.models import BaseModel


class MeetingRoom(BaseModel):
    """会议室。"""

    class Status(models.TextChoices):
        AVAILABLE = "available", "可用"
        MAINTAIN = "maintain", "维护中"

    name = models.CharField("会议室名称", max_length=100)
    location = models.CharField("位置", max_length=200, blank=True, default="")
    capacity = models.IntegerField("可容纳人数", default=0)
    facilities = models.CharField("配套设施", max_length=255, blank=True, default="")
    equipment = models.CharField("设备", max_length=255, blank=True, default="")
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    description = models.TextField("说明", blank=True, default="")

    class Meta:
        db_table = "meeting_room"
        verbose_name = "会议室"
        verbose_name_plural = "会议室"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}({self.location})"


class MeetingBooking(BaseModel):
    """会议预约。"""

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "待开始"
        ONGOING = "ongoing", "进行中"
        ENDED = "ended", "已结束"
        CANCELLED = "cancelled", "已取消"

    room = models.ForeignKey(MeetingRoom, on_delete=models.CASCADE, related_name="bookings", verbose_name="会议室")
    title = models.CharField("会议主题", max_length=200)
    organizer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                  related_name="meeting_bookings", verbose_name="组织者")
    attendees = models.ManyToManyField("accounts.User", related_name="meetings_attended", blank=True,
                                      verbose_name="参会人")
    start = models.DateTimeField("开始时间")
    end = models.DateTimeField("结束时间")
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.UPCOMING)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "meeting_booking"
        verbose_name = "会议预约"
        verbose_name_plural = "会议预约"
        ordering = ["-start"]

    def __str__(self):
        return self.title


class MeetingMinute(BaseModel):
    """会议纪要。"""

    booking = models.ForeignKey(MeetingBooking, on_delete=models.CASCADE, related_name="minutes", verbose_name="关联预约")
    title = models.CharField("纪要标题", max_length=200)
    content = models.TextField("纪要内容", blank=True, default="")
    uploader = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                 related_name="meeting_minutes", verbose_name="记录人")
    file = models.CharField("附件路径", max_length=500, blank=True, default="")
    original_name = models.CharField("原始文件名", max_length=255, blank=True, default="")

    class Meta:
        db_table = "meeting_minute"
        verbose_name = "会议纪要"
        verbose_name_plural = "会议纪要"
        ordering = ["-created_at"]
