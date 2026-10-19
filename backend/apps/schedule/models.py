"""日程与任务域模型。"""
from django.db import models

from apps.common.models import BaseModel


class Schedule(BaseModel):
    """个人 / 团队日程。"""

    class Category(models.TextChoices):
        MEETING = "meeting", "会议"
        TASK = "task", "任务"
        REMINDER = "reminder", "提醒"
        OTHER = "other", "其他"

    class Status(models.TextChoices):
        ACTIVE = "active", "生效中"
        DONE = "done", "已完成"
        CANCELLED = "cancelled", "已取消"

    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容", blank=True, default="")
    owner = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                              related_name="schedules", verbose_name="归属人")
    participants = models.ManyToManyField("accounts.User", related_name="schedule_shared", blank=True,
                                          verbose_name="参与人")
    start = models.DateTimeField("开始时间")
    end = models.DateTimeField("结束时间", null=True, blank=True)
    all_day = models.BooleanField("全天", default=False)
    location = models.CharField("地点", max_length=200, blank=True, default="")
    category = models.CharField("类别", max_length=20, choices=Category.choices, default=Category.OTHER)
    remind_before = models.IntegerField("提前提醒(分钟)", default=0)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "schedule"
        verbose_name = "日程"
        verbose_name_plural = "日程"
        ordering = ["-start"]


class Task(BaseModel):
    """看板任务（轻量项目协作）。"""

    class Status(models.TextChoices):
        TODO = "todo", "待办"
        DOING = "doing", "进行中"
        DONE = "done", "已完成"

    class Priority(models.TextChoices):
        LOW = "low", "低"
        MID = "mid", "中"
        HIGH = "high", "高"

    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容", blank=True, default="")
    assignee = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                 related_name="tasks_assigned", verbose_name="负责人")
    creator = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                related_name="tasks_created", verbose_name="创建人")
    start = models.DateTimeField("开始时间", null=True, blank=True)
    due = models.DateTimeField("截止时间", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField("优先级", max_length=20, choices=Priority.choices, default=Priority.MID)
    progress = models.IntegerField("进度(%)", default=0)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="children", verbose_name="父任务")
    tags = models.CharField("标签", max_length=255, blank=True, default="")

    class Meta:
        db_table = "task"
        verbose_name = "任务"
        verbose_name_plural = "任务"
        ordering = ["-priority", "due"]
