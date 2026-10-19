"""考勤域冒烟测试（ORM 层，无需启动服务）。

用法：
    python scripts/smoke_attendance.py
"""
import os
import random
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.attendance import services  # noqa: E402
from apps.attendance.models import (  # noqa: E402
    AttendanceDaily,
    AttendanceException,
    AttendanceRule,
    PunchRecord,
)
from apps.workflow.models import (  # noqa: E402
    CardReissueRequest,
    LeaveRequest,
    OvertimeRequest,
    TripRequest,
)

_results = []


def check(label, cond, detail=""):
    _results.append((label, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")
    return cond


def _doc_covers(user, day):
    """当天是否已被生效单据覆盖（出差/请假/加班/补卡）。

    有覆盖时考勤日报会按单据判定（出差优先级高于缺卡/旷工），
    这类日期不能用来验证「无打卡 -> 缺卡/旷工」。
    """
    lo = timezone.make_aware(datetime.combine(day, time(0, 0)))
    hi = timezone.make_aware(datetime.combine(day, time(23, 59, 59)))
    for M in (LeaveRequest, TripRequest, OvertimeRequest):
        for r in M.objects.filter(applicant=user, status=M.Status.APPROVED):
            s, e = getattr(r, "start_at", None), getattr(r, "end_at", None)
            if s and e and s <= hi and e >= lo:
                return True
    if CardReissueRequest.objects.filter(applicant=user, status=CardReissueRequest.Status.APPROVED,
                                         miss_date=day).exists():
        return True
    return False


def free_workday(start, user, rule):
    """从 start 往过去找最近一个「工作日 且 无单据覆盖」的日期。"""
    d = start
    for _ in range(90):
        if d.isoweekday() in rule.effective_workdays and not _doc_covers(user, d):
            return d
        d -= timedelta(days=1)
    return d


def clear(user):
    PunchRecord.all_objects.filter(user=user).delete()
    AttendanceDaily.all_objects.filter(user=user).delete()
    AttendanceException.all_objects.filter(user=user).delete()


def add_punch(user, day, hh, mm, minute_offset=0):
    return PunchRecord.objects.create(
        user=user,
        punch_at=timezone.make_aware(datetime.combine(day, time(hh, mm))),
        punch_date=day,
    )


def main():
    random.seed(42)
    user = User.objects.filter(username="liuyang").first()
    assert user is not None, "缺少演示账号 liuyang，请先执行 init_base"
    rule = services.get_rule_for_user(user)
    print("\n== 1. 基础环境与规则 ==")
    check("存在默认考勤规则", rule is not None, f"规则={rule}")
    check("默认班次为 09:00-18:00", rule.work_start.strftime("%H:%M") == "09:00"
          and rule.work_end.strftime("%H:%M") == "18:00")

    clear(user)
    today = timezone.localdate()
    # 选一个「工作日且无单据覆盖」的日期（否则会被出差/请假等单据改写状态）
    day = free_workday(today, user, rule)

    print("\n== 2. 正常出勤 ==")
    add_punch(user, day, 8, 55)
    add_punch(user, day, 18, 5)
    d = services.rebuild_daily(user, day)
    check("正常出勤状态", d.status == AttendanceDaily.Status.NORMAL, f"status={d.status} remark={d.remark}")
    check("工时计算正确", d.work_minutes == 550, f"work_minutes={d.work_minutes}")

    print("\n== 3. 迟到（超过 15 分钟宽限）==")
    day2 = free_workday(day - timedelta(days=1), user, rule)
    add_punch(user, day2, 9, 40)
    add_punch(user, day2, 18, 10)
    d2 = services.rebuild_daily(user, day2)
    check("迟到状态判定", d2.status == AttendanceDaily.Status.LATE, f"status={d2.status} remark={d2.remark}")
    check("迟到分钟数", d2.late_minutes == 40, f"late_minutes={d2.late_minutes}")
    exc = AttendanceException.objects.filter(user=user, date=day2).first()
    check("自动生成迟到异常", exc is not None and exc.type == AttendanceException.Type.LATE,
          f"异常={exc.type if exc else None}")

    print("\n== 4. 缺下班卡 ==")
    day3 = free_workday(day2 - timedelta(days=1), user, rule)
    add_punch(user, day3, 8, 50)
    d3 = services.rebuild_daily(user, day3)
    check("缺卡状态判定", d3.status == AttendanceDaily.Status.MISS, f"status={d3.status} remark={d3.remark}")
    check("缺卡类型为缺下班卡",
          AttendanceException.objects.filter(user=user, date=day3,
                                             type=AttendanceException.Type.MISS_OUT).exists())

    print("\n== 5. 旷工（无打卡）==")
    day4 = free_workday(day3 - timedelta(days=1), user, rule)
    d4 = services.rebuild_daily(user, day4)
    check("旷工状态判定", d4.status == AttendanceDaily.Status.ABSENT, f"status={d4.status}")
    check("生成旷工异常",
          AttendanceException.objects.filter(user=user, date=day4,
                                             type=AttendanceException.Type.ABSENT).exists())

    print("\n== 6. 休息日不计异常 ==")
    rest = day
    while rest.isoweekday() in rule.effective_workdays:
        rest += timedelta(days=1)
    d5 = services.rebuild_daily(user, rest)
    check("周末判定为休息", d5.status in (AttendanceDaily.Status.REST, AttendanceDaily.Status.HOLIDAY),
          f"status={d5.status}")

    print("\n== 7. 请假覆盖 ==")
    # 先硬删除历史冒烟请假：软删除的记录仍占用 code 唯一键，
    # 而 random.seed(42) 每次都会生成同一个单号，脚本第二次运行必然
    # Duplicate entry 失败。单号改用 uuid，彻底避免撞号。
    from uuid import uuid4

    # 先把「本次运行前本来就可见」的请假单 id 记下来，跑完原样还原。
    # 否则这行 update 每跑一次就把该用户的请假数据永久软删一次，演示库会单调流失数据。
    preexisting_leave_ids = list(
        LeaveRequest.objects.filter(applicant=user, is_deleted=False).values_list("id", flat=True)
    )
    LeaveRequest.all_objects.filter(applicant=user, title="冒烟请假").delete()
    LeaveRequest.objects.filter(applicant=user, is_deleted=False).update(is_deleted=True)
    LeaveRequest.objects.create(
        applicant=user, code=f"LV-SMOKE-{uuid4().hex[:8]}", title="冒烟请假",
        status=LeaveRequest.Status.APPROVED, start_at=timezone.make_aware(datetime.combine(day4, time(9, 0))),
        end_at=timezone.make_aware(datetime.combine(day4, time(18, 0))), days=1,
    )
    d4 = services.rebuild_daily(user, day4)
    check("请假日期覆盖旷工", d4.status == AttendanceDaily.Status.LEAVE, f"status={d4.status}")
    check("旷工异常自动关闭",
          AttendanceException.objects.filter(user=user, date=day4,
                                             type=AttendanceException.Type.ABSENT,
                                             status=AttendanceException.Status.IGNORED).exists())

    print("\n== 8. 异常处理 ==")
    pending = AttendanceException.objects.filter(user=user,
                                                 status=AttendanceException.Status.PENDING).first()
    if pending:
        handled = services.handle_exception(pending.id, user, "冒烟测试：确认无误")
        check("异常处理成功", handled.status == AttendanceException.Status.HANDLED,
              f"status={handled.status} result={handled.handle_result}")
    else:
        check("存在待处理异常", False, "未生成任何待处理异常")

    print("\n== 9. 批量重建与月度汇总 ==")
    start = date(today.year, today.month, 1)
    for offset in range(0, 15):
        dd = start + timedelta(days=offset)
        if dd.isoweekday() not in rule.effective_workdays:
            continue
        if PunchRecord.objects.filter(user=user, punch_date=dd).exists():
            continue
        add_punch(user, dd, random.choice([8, 9]), random.choice([45, 50, 55, 5]))
        add_punch(user, dd, 18, random.choice([2, 10, 25, 45]))
    n = services.rebuild_range(start, today, [user])
    check("批量重建返回处理量", n > 0, f"人日={n}")
    month = today.strftime("%Y-%m")
    summary = services.month_summary(user, month, rebuild=True)
    check("月度汇总出勤天数", summary.present_days > 0, f"出勤={summary.present_days}/{summary.work_days}")
    check("出勤率为正数", 0 <= float(summary.attendance_rate) <= 100, f"出勤率={summary.attendance_rate}")

    print("\n== 10. 部门汇总与导出 ==")
    rows = services.dept_summary(month, user.dept_id)
    check("部门汇总包含本人", any(r["user_id"] == user.id for r in rows), f"行数={len(rows)}")
    export = services.export_rows(services.daily_queryset_for_user(user, {"start_date": start}))
    check("导出包含表头与数据行", len(export) > 1, f"行数={len(export) - 1}")

    print("\n== 11. 清理冒烟数据 ==")
    # 上面「请假覆盖」用的请假单是绕开审批流直接建的（无 workflow_instance、status=approved）。
    # 若不清理，它会作为一条「已通过、却没有任何审批轨迹」的假数据留在演示库的请假列表里，
    # 也会让「明细未关联流程实例」的完整性检查恒为 1。
    # 脚本开头已按标题清过一次（防止 code 唯一键撞号），这里在结尾再清一次，保证跑完不留残迹。
    smoke_leaves = LeaveRequest.all_objects.filter(applicant=user, title="冒烟请假")
    n_leave = smoke_leaves.count()
    smoke_leaves.delete()
    check("冒烟请假单已清理",
          LeaveRequest.all_objects.filter(applicant=user, title="冒烟请假").count() == 0,
          f"清理 {n_leave} 条")

    # 还原运行前就该可见的请假单，保证冒烟跑 N 次与跑 0 次的演示数据一致。
    restored = LeaveRequest.all_objects.filter(
        id__in=preexisting_leave_ids, is_deleted=True
    ).update(is_deleted=False)
    check("运行前已有请假单已还原",
          LeaveRequest.objects.filter(id__in=preexisting_leave_ids).count() == len(preexisting_leave_ids),
          f"还原 {restored}/{len(preexisting_leave_ids)} 条")

    total = len(_results)
    passed = sum(1 for _, c in _results if c)
    print(f"\n==== 考勤冒烟结果：{passed}/{total} 通过 ====")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
