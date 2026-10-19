"""补齐演示数据：公告、文档、会议、看板任务，并回填人事合同/培训日期。

    python manage.py seed_extras

命令幂等：已存在同名数据时跳过，可重复执行。
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Department, User
from apps.announcement.models import Announcement, AnnouncementRead
from apps.document.models import Document
from apps.hr.models import Contract, Training
from apps.meeting.models import MeetingBooking, MeetingMinute, MeetingRoom
from apps.schedule.models import Task as ScheduleTask

ANNOUNCEMENTS = [
    ("关于 2026 年国庆节放假安排的通知", "notice", "important", True,
     "根据国务院办公厅通知，10 月 1 日至 10 月 7 日放假调休，共 7 天。请各部门提前安排值班人员，"
     "并在放假前完成设备断电与资料归档。"),
    ("公司考勤管理制度（2026 修订版）", "policy", "normal", False,
     "修订要点：1) 弹性上班时间为 09:00-09:30；2) 迟到 30 分钟以内不计旷工；"
     "3) 外勤打卡需上传定位与事由，由直属主管审批。"),
    ("新版 OA 系统上线公告", "announcement", "urgent", True,
     "新版 OA 系统已上线，覆盖流程审批、考勤、报销、公告、文档、会议与智能看板。"
     "如遇权限或流程异常，请联系信息中心。"),
    ("2026 年第三季度全员大会纪要", "announcement", "normal", False,
     "会议通报了第三季度经营情况与第四季度重点目标，并表彰了季度优秀员工。"),
    ("关于开展消防安全演练的通知", "notice", "important", False,
     "定于本月 25 日 15:00 在园区广场开展消防疏散演练，请全体员工参加并签到。"),
]

DOCS = [
    ("员工手册", "doc", "all", 3),
    ("报销制度与流程说明", "doc", "all", 2),
    ("年度培训计划", "doc", "all", 1),
    ("产品需求说明书 v2", "doc", "dept", 1),
]

ROOMS = [
    ("第一会议室", "A 座 3 层 301", 12, "投影、白板", "视频会议终端"),
    ("第二会议室", "A 座 3 层 302", 8, "投影", "电视投屏"),
    ("多功能厅", "B 座 1 层", 60, "音响、舞台", "话筒 4 支"),
    ("洽谈室", "A 座 2 层 205", 4, "白板", "无"),
]

TASKS = [
    ("梳理 Q4 产品路线图", "doing", "high", 60, 7),
    ("完成 OA 系统权限矩阵自检", "done", "high", 100, -3),
    ("整理季度考勤异常清单", "todo", "mid", 0, 5),
    ("输出报销制度培训材料", "doing", "mid", 40, 10),
    ("更新会议室设备清单", "todo", "low", 0, 14),
    ("归档第三季度合同扫描件", "done", "mid", 100, -1),
]


class Command(BaseCommand):
    help = "补齐公告 / 文档 / 会议 / 看板任务演示数据，并回填人事日期字段"

    def handle(self, *args, **opts):
        now = timezone.now()
        admin = User.objects.filter(username="admin").first()
        hr = User.objects.filter(username="lina").first() or admin
        staff = User.objects.filter(username="sunli").first() or admin
        mgr = User.objects.filter(username="zhangwei").first() or admin
        emp = User.objects.filter(username="liuyang").first() or admin
        dept = Department.objects.filter(name__contains="行政").first() or Department.objects.first()

        self.stdout.write(self.style.HTTP_INFO("== 公告 =="))
        created = 0
        for i, (title, cat, level, top, content) in enumerate(ANNOUNCEMENTS):
            ann, is_new = Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "content": content, "category": cat, "level": level,
                    "status": Announcement.Status.PUBLISHED, "publisher": staff if cat != "policy" else hr,
                    "dept": dept, "is_top": top,
                    "published_at": now - timedelta(days=i * 2),
                    "read_count": (len(ANNOUNCEMENTS) - i) * 3,
                },
            )
            if is_new:
                created += 1
                for u in [admin, hr, mgr, emp]:
                    AnnouncementRead.objects.get_or_create(announcement=ann, user=u)
        self.stdout.write(f"  新增公告 {created} 条，现有 {Announcement.objects.count()} 条")

        self.stdout.write(self.style.HTTP_INFO("== 文档 =="))
        folder, _ = Document.objects.get_or_create(
            name="制度与手册", defaults={"is_folder": True, "owner": staff, "dept": dept,
                                        "share_type": Document.ShareType.ALL, "category": Document.Category.DOC})
        created = 0
        for name, cat, share, ver in DOCS:
            _, is_new = Document.objects.get_or_create(
                name=name,
                defaults={
                    "parent": folder, "is_folder": False, "category": cat, "owner": staff, "dept": dept,
                    "original_name": f"{name}.pdf", "mime": "application/pdf",
                    "size": 120 * 1024, "version": ver, "share_type": share,
                    "tags": "制度,内部", "description": f"{name}（演示数据，未绑定真实文件）",
                    "download_count": ver * 2,
                },
            )
            created += 1 if is_new else 0
        self.stdout.write(f"  新增文档 {created} 条，现有 {Document.objects.count()} 条")

        self.stdout.write(self.style.HTTP_INFO("== 会议 =="))
        room_count = 0
        rooms = []
        for name, loc, cap, fac, eq in ROOMS:
            room, is_new = MeetingRoom.objects.get_or_create(
                name=name, defaults={"location": loc, "capacity": cap, "facilities": fac,
                                     "equipment": eq, "status": MeetingRoom.Status.AVAILABLE})
            rooms.append(room)
            room_count += 1 if is_new else 0
        base = now.replace(hour=10, minute=0, second=0, microsecond=0)
        bookings = [
            ("周例会", 0, 1, MeetingBooking.Status.UPCOMING, admin),
            ("产品评审会", 1, 3, MeetingBooking.Status.UPCOMING, mgr),
            ("季度总结会", 2, -2, MeetingBooking.Status.ENDED, hr),
        ]
        bk_count = 0
        ended = None
        for title, room_i, day_off, status, owner in bookings:
            start = base + timedelta(days=day_off)
            bk, is_new = MeetingBooking.objects.get_or_create(
                title=title,
                defaults={"room": rooms[room_i], "organizer": owner, "start": start,
                          "end": start + timedelta(hours=1), "status": status,
                          "remark": "演示数据"})
            bk_count += 1 if is_new else 0
            if is_new:
                bk.attendees.set([u for u in [admin, hr, mgr, emp] if u])
            if status == MeetingBooking.Status.ENDED:
                ended = bk
        mi_count = 0
        if ended is not None:
            for mt, content in [("季度总结会会议纪要", "1) 通报季度指标达成情况；2) 明确 Q4 重点项目与责任人。")]:
                _, is_new = MeetingMinute.objects.get_or_create(
                    booking=ended, title=mt,
                    defaults={"content": content, "uploader": hr, "original_name": "meeting-minute.pdf"})
                mi_count += 1 if is_new else 0
        self.stdout.write(f"  新增会议室 {room_count} / 预约 {bk_count} / 纪要 {mi_count}")
        self.stdout.write(f"  现有 会议室 {MeetingRoom.objects.count()} / 预约 {MeetingBooking.objects.count()} "
                          f"/ 纪要 {MeetingMinute.objects.count()}")

        self.stdout.write(self.style.HTTP_INFO("== 看板任务 =="))
        t_count = 0
        for i, (title, status, prio, prog, due_off) in enumerate(TASKS):
            _, is_new = ScheduleTask.objects.get_or_create(
                title=title,
                defaults={"assignee": [admin, hr, mgr, emp][i % 4], "creator": admin,
                          "start": now - timedelta(days=3),
                          "due": now + timedelta(days=due_off),
                          "status": status, "priority": prio, "progress": prog,
                          "tags": "演示", "content": "演示任务"})
            t_count += 1 if is_new else 0
        self.stdout.write(f"  新增任务 {t_count} 条，现有 {ScheduleTask.objects.count()} 条")

        self.stdout.write(self.style.HTTP_INFO("== 回填人事日期 =="))
        fixed_c = 0
        for c in Contract.objects.all():
            if c.sign_date and c.start_date and c.end_date:
                continue
            c.sign_date = c.sign_date or (now - timedelta(days=240)).date()
            c.start_date = c.start_date or (now - timedelta(days=210)).date()
            c.end_date = c.end_date or (now + timedelta(days=155)).date()
            c.save(update_fields=["sign_date", "start_date", "end_date"])
            fixed_c += 1
        fixed_t = 0
        for t in Training.objects.all():
            if t.start_date:
                continue
            t.start_date = (now - timedelta(days=45)).date()
            t.save(update_fields=["start_date"])
            fixed_t += 1
        self.stdout.write(f"  回填合同日期 {fixed_c} 条 / 培训日期 {fixed_t} 条")

        self.stdout.write(self.style.SUCCESS("演示数据补齐完成"))
