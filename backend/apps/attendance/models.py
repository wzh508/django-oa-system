"""考勤域模型。

设计要点：
- 考勤规则（班次）支持按部门维度下发，未指定部门表示全公司默认规则。
- 打卡记录只追加；日报表由 services 重新计算（幂等），支持任意区间重建。
- 请假/出差/加班/补卡等单据来自 workflow 域，本模块只读引用，不复制数据。
"""
from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class AttendanceRule(BaseModel):
    """考勤规则（班次）。"""

    name = models.CharField("规则名称", max_length=64)
    code = models.CharField("规则编码", max_length=64, unique=True)
    work_start = models.TimeField("上班时间")
    work_end = models.TimeField("下班时间")
    work_minutes = models.IntegerField("标准工时（分钟）", default=480)
    late_minutes = models.IntegerField("迟到宽限（分钟）", default=15)
    early_leave_minutes = models.IntegerField("早退宽限（分钟）", default=15)
    absent_minutes = models.IntegerField("旷工判定阈值（分钟）", default=120,
                                         help_text="迟到/早退累计超过该值视为旷工")
    overtime_min_minutes = models.IntegerField("加班起算时长（分钟）", default=60)
    workdays = models.JSONField("工作日", default=list, blank=True,
                                help_text="ISO 周内序号：1=周一 … 7=周日；为空表示默认周一至周五")
    dept_ids = models.JSONField("适用部门", default=list, blank=True,
                                help_text="为空表示适用全公司")
    is_default = models.BooleanField("默认规则", default=False, db_index=True)
    enabled = models.BooleanField("启用", default=True)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "考勤规则"
        verbose_name_plural = "考勤规则"
        ordering = ["-is_default", "id"]

    def __str__(self):
        return f"{self.name}({self.work_start.strftime('%H:%M')}-{self.work_end.strftime('%H:%M')})"

    @property
    def effective_workdays(self) -> list:
        return self.workdays or [1, 2, 3, 4, 5]


class AttendanceHoliday(BaseModel):
    """节假日 / 调休日历。用于生成考勤日报时跳过法定休息日。"""

    class Type(models.TextChoices):
        HOLIDAY = "holiday", "法定节假日"
        WORKDAY = "workday", "调休上班"
        COMPANY = "company", "公司福利假"

    date = models.DateField("日期", unique=True, db_index=True)
    name = models.CharField("名称", max_length=64)
    type = models.CharField("类型", max_length=16, choices=Type.choices, default=Type.HOLIDAY)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "节假日日历"
        verbose_name_plural = "节假日日历"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class PunchRecord(BaseModel):
    """原始打卡流水（只追加）。"""

    class PunchType(models.TextChoices):
        IN = "in", "上班卡"
        OUT = "out", "下班卡"
        AUTO = "auto", "自动推断"

    class Source(models.TextChoices):
        WEB = "web", "网页端"
        APP = "app", "移动端"
        DEVICE = "device", "考勤机"
        ADMIN = "admin", "管理员补录"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="员工", on_delete=models.CASCADE,
                             related_name="punches", db_index=True)
    punch_at = models.DateTimeField("打卡时间", db_index=True)
    punch_date = models.DateField("归属日期", db_index=True)
    punch_type = models.CharField("打卡类型", max_length=8, choices=PunchType.choices, default=PunchType.AUTO)
    source = models.CharField("来源", max_length=16, choices=Source.choices, default=Source.WEB)
    location = models.CharField("打卡地点", max_length=255, blank=True, default="")
    device = models.CharField("设备", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "打卡记录"
        verbose_name_plural = "打卡记录"
        ordering = ["punch_at"]
        indexes = [models.Index(fields=["user", "punch_date"])]

    def __str__(self):
        return f"{self.user_id} {self.punch_at:%Y-%m-%d %H:%M}"


class AttendanceDaily(BaseModel):
    """考勤日报：由打卡流水 + 规则 + 已通过单据计算得到的当日结果。"""

    class Status(models.TextChoices):
        NORMAL = "normal", "正常"
        LATE = "late", "迟到"
        EARLY_LEAVE = "early_leave", "早退"
        ABSENT = "absent", "旷工"
        MISS = "miss", "缺卡"
        LEAVE = "leave", "请假"
        TRIP = "trip", "出差"
        REST = "rest", "休息日"
        HOLIDAY = "holiday", "法定节假日"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="员工", on_delete=models.CASCADE,
                             related_name="attendance_dailies", db_index=True)
    date = models.DateField("日期", db_index=True)
    rule = models.ForeignKey(AttendanceRule, verbose_name="适用规则", null=True, blank=True,
                             on_delete=models.SET_NULL)
    sign_in_at = models.DateTimeField("上班打卡", null=True, blank=True)
    sign_out_at = models.DateTimeField("下班打卡", null=True, blank=True)
    work_minutes = models.IntegerField("实际工时（分钟）", default=0)
    late_minutes = models.IntegerField("迟到（分钟）", default=0)
    early_minutes = models.IntegerField("早退（分钟）", default=0)
    overtime_minutes = models.IntegerField("加班（分钟）", default=0)
    status = models.CharField("考勤状态", max_length=16, choices=Status.choices, default=Status.NORMAL, db_index=True)
    punch_count = models.IntegerField("打卡次数", default=0)
    source = models.CharField("数据来源", max_length=16, default="auto",
                              choices=[("auto", "系统计算"), ("manual", "人工修正")])
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "考勤日报"
        verbose_name_plural = "考勤日报"
        unique_together = ("user", "date")
        ordering = ["-date", "id"]
        indexes = [models.Index(fields=["date", "status"]), models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user_id} {self.date} {self.get_status_display()}"


class AttendanceException(BaseModel):
    """异常考勤（迟到/早退/缺卡/旷工），需人工确认或关联補卡流程。"""

    class Type(models.TextChoices):
        LATE = "late", "迟到"
        EARLY_LEAVE = "early_leave", "早退"
        MISS_IN = "miss_in", "缺上班卡"
        MISS_OUT = "miss_out", "缺下班卡"
        ABSENT = "absent", "旷工"

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        HANDLED = "handled", "已处理"
        IGNORED = "ignored", "已忽略"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="员工", on_delete=models.CASCADE,
                             related_name="attendance_exceptions", db_index=True)
    date = models.DateField("日期", db_index=True)
    type = models.CharField("异常类型", max_length=16, choices=Type.choices, db_index=True)
    minutes = models.IntegerField("时长（分钟）", default=0)
    status = models.CharField("处理状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    reason = models.CharField("异常说明", max_length=255, blank=True, default="")
    handler = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="处理人", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="handled_exceptions")
    handle_result = models.CharField("处理结果", max_length=255, blank=True, default="")
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        verbose_name = "考勤异常"
        verbose_name_plural = "考勤异常"
        unique_together = ("user", "date", "type")
        ordering = ["-date", "id"]
        indexes = [models.Index(fields=["status", "date"])]

    def __str__(self):
        return f"{self.user_id} {self.date} {self.get_type_display()}"


class AttendanceSummary(BaseModel):
    """月度汇总（按需计算后落库，避免每次实时聚合）。"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="员工", on_delete=models.CASCADE,
                             related_name="attendance_summaries", db_index=True)
    month = models.CharField("月份", max_length=7, db_index=True, help_text="格式 YYYY-MM")
    work_days = models.IntegerField("应出勤天数", default=0)
    present_days = models.IntegerField("实际出勤", default=0)
    late_count = models.IntegerField("迟到次数", default=0)
    early_count = models.IntegerField("早退次数", default=0)
    absent_count = models.IntegerField("旷工次数", default=0)
    miss_count = models.IntegerField("缺卡次数", default=0)
    leave_days = models.DecimalField("请假天数", max_digits=6, decimal_places=1, default=0)
    work_minutes = models.IntegerField("累计工时（分钟）", default=0)
    overtime_minutes = models.IntegerField("累计加班（分钟）", default=0)
    attendance_rate = models.DecimalField("出勤率", max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = "考勤月度汇总"
        verbose_name_plural = "考勤月度汇总"
        unique_together = ("user", "month")
        ordering = ["-month", "id"]

    def __str__(self):
        return f"{self.user_id} {self.month}"
