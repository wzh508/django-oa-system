"""初始化考勤基础数据：默认班次、弹性班次、年度法定节假日。

幂等：重复执行不会产生重复数据。
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.attendance.models import AttendanceHoliday, AttendanceRule

# 常见节假日（月-日, 名称）。跨年差异可按需调整或用 --year 指定后手动修正。
CN_HOLIDAYS_2026 = [
    ((1, 1), "元旦"), ((1, 2), "元旦调休"), ((1, 3), "元旦调休"),
    ((2, 15), "春节假期"), ((2, 16), "除夕"), ((2, 17), "春节"), ((2, 18), "春节调休"),
    ((2, 19), "春节调休"), ((2, 20), "春节调休"), ((2, 21), "春节调休"),
    ((4, 4), "清明节"), ((4, 5), "清明调休"), ((4, 6), "清明调休"),
    ((5, 1), "劳动节"), ((5, 2), "劳动节调休"), ((5, 3), "劳动节调休"),
    ((5, 4), "劳动节调休"), ((5, 5), "劳动节调休"),
    ((6, 19), "端午节"), ((6, 20), "端午调休"), ((6, 21), "端午调休"),
    ((9, 25), "中秋节"), ((9, 26), "中秋调休"), ((9, 27), "中秋调休"),
    ((10, 1), "国庆节"), ((10, 2), "国庆调休"), ((10, 3), "国庆调休"),
    ((10, 4), "国庆调休"), ((10, 5), "国庆调休"), ((10, 6), "国庆调休"),
    ((10, 7), "国庆调休"), ((10, 8), "国庆调休"),
]


class Command(BaseCommand):
    help = "初始化考勤规则与节假日日历"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=date.today().year)
        parser.add_argument("--reset-holidays", action="store_true", help="重置当年节假日")

    def handle(self, *args, **opts):
        year = opts["year"]
        self._init_rules()
        self._init_holidays(year, opts["reset_holidays"])
        self.stdout.write(self.style.SUCCESS("init_attendance 完成"))

    def _init_rules(self):
        specs = [
            {
                "code": "STD", "name": "标准班次 09:00-18:00", "is_default": True,
                "work_start": "09:00", "work_end": "18:00", "work_minutes": 480,
                "late_minutes": 15, "early_leave_minutes": 15, "absent_minutes": 120,
                "overtime_min_minutes": 60, "dept_ids": [], "remark": "全公司默认班次",
            },
            {
                "code": "FLEX", "name": "弹性班次 09:30-18:30", "is_default": False,
                "work_start": "09:30", "work_end": "18:30", "work_minutes": 480,
                "late_minutes": 30, "early_leave_minutes": 30, "absent_minutes": 180,
                "overtime_min_minutes": 60, "dept_ids": [], "remark": "弹性工作制",
            },
            {
                "code": "SHIFT", "name": "轮班 08:00-17:00", "is_default": False,
                "work_start": "08:00", "work_end": "17:00", "work_minutes": 480,
                "late_minutes": 10, "early_leave_minutes": 10, "absent_minutes": 90,
                "overtime_min_minutes": 30, "dept_ids": [], "remark": "行政/前台等早班",
            },
        ]
        for spec in specs:
            AttendanceRule.objects.update_or_create(
                code=spec["code"],
                defaults={**spec, "workdays": [1, 2, 3, 4, 5], "enabled": True},
            )
        self.stdout.write(f"  考勤规则：总计 {AttendanceRule.objects.count()}")

    def _init_holidays(self, year, reset=False):
        if reset:
            AttendanceHoliday.objects.filter(date__year=year).delete()
        created = 0
        for (month, day), name in CN_HOLIDAYS_2026:
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            _, ok = AttendanceHoliday.objects.get_or_create(
                date=d, defaults={"name": name, "type": AttendanceHoliday.Type.HOLIDAY},
            )
            created += 1 if ok else 0
        self.stdout.write(f"  节假日：新增 {created} / {year} 年总计 "
                          f"{AttendanceHoliday.objects.filter(date__year=year).count()}")
