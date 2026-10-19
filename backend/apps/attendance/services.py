"""考勤业务服务层。

所有计算逻辑集中在此，View 只负责参数校验与响应组装。
核心是 rebuild_daily：读取「打卡流水 + 考勤规则 + 已通过的流程单据」重算当日结果，
函数幂等，任意区间可重复执行。
"""
import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Department, User
from apps.common.exceptions import BusinessException
from apps.common.notify import notify_user

from .models import (
    AttendanceDaily,
    AttendanceException,
    AttendanceHoliday,
    AttendanceRule,
    AttendanceSummary,
    PunchRecord,
)

logger = logging.getLogger(__name__)

DEFAULT_WORKDAYS = [1, 2, 3, 4, 5]


# ---------------------------------------------------------------- 规则
def get_default_rule() -> AttendanceRule | None:
    """返回默认规则；没有显式默认时取第一条启用规则。"""
    rule = AttendanceRule.objects.filter(is_default=True, enabled=True, is_deleted=False).first()
    if rule is None:
        rule = AttendanceRule.objects.filter(enabled=True, is_deleted=False).first()
    return rule


def get_rule_for_user(user: User) -> AttendanceRule | None:
    """按部门优先、其次默认规则为员工解析适用规则。"""
    dept_id = getattr(user, "dept_id", None)
    if dept_id:
        scoped = AttendanceRule.objects.filter(enabled=True, is_deleted=False, is_default=False)
        for rule in scoped:
            ids = rule.dept_ids or []
            if dept_id in ids:
                return rule
    return get_default_rule()


def make_aware(date, tm: time) -> datetime:
    """把 date 与 time 组合成带时区的 datetime。"""
    return timezone.make_aware(datetime.combine(date, tm))


# ---------------------------------------------------------------- 打卡
@transaction.atomic
def punch(user: User, punch_at=None, punch_type: str = "auto", source: str = "web",
          location: str = "", device: str = "", remark: str = "") -> PunchRecord:
    """记录一次打卡，并同步重算当日日报。

    Args:
        user: 打卡员工。
        punch_at: 打卡时刻，为空表示当前时间。
        punch_type: in / out / auto。
        source: web / app / device / admin。
        location: 打卡地点描述。
        device: 设备标识。
        remark: 备注。

    Returns:
        新建的 PunchRecord。

    Raises:
        BusinessException: 打卡时间超出合理范围（早于当天 00:00 或晚于明天）。
    """
    now = timezone.localtime()
    moment = punch_at or now
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    moment = timezone.localtime(moment)
    if moment.date() < now.date() - timedelta(days=1) or moment > now + timedelta(minutes=5):
        raise BusinessException("打卡时间不在有效范围内")

    record = PunchRecord.objects.create(
        user=user, punch_at=moment, punch_date=moment.date(), punch_type=punch_type,
        source=source, location=location, device=device, remark=remark, created_by=user,
    )
    rebuild_daily(user, moment.date())
    return record


# ---------------------------------------------------------------- 单据上下文
def _approved_leave_days(user: User, date) -> Decimal:
    """返回该员工在这一天已被批准的请假天数（0 / 0.5 / 1）。"""
    from apps.workflow.models import LeaveRequest

    qs = LeaveRequest.objects.filter(
        applicant=user, status=LeaveRequest.Status.APPROVED, is_deleted=False,
        start_at__lte=make_aware(date, time(23, 59, 59)),
        end_at__gte=make_aware(date, time(0, 0)),
    )
    total = Decimal("0")
    for req in qs:
        if req.start_at and req.end_at:
            start = timezone.localtime(req.start_at)
            end = timezone.localtime(req.end_at)
            if start.date() <= date <= end.date():
                # 同一天内的部分请假按整天计（中小企业场景常见做法）
                total += Decimal("1")
    return total


def _has_approved(user: User, date, model) -> bool:
    """判断指定的流程单据在该日期是否存在已通过记录。"""
    qs = model.objects.filter(applicant=user, status=model.Status.APPROVED, is_deleted=False)
    return qs.filter(start_at__lte=make_aware(date, time(23, 59, 59)),
                     end_at__gte=make_aware(date, time(0, 0))).exists()


def _approved_cardifies(user: User, date) -> dict:
    """返回当天已通过的补卡申请覆盖情况 {"in": bool, "out": bool}。"""
    from apps.workflow.models import CardReissueRequest

    covered = {"in": False, "out": False}
    qs = CardReissueRequest.objects.filter(
        applicant=user, status=CardReissueRequest.Status.APPROVED, is_deleted=False, miss_date=date
    )
    # 注意：模型的 miss_type 取值为 sign_in / sign_out，而调用方统一按 in / out 读取，
    # 早期实现直接用 covered[req.miss_type] 赋值，导致键名不匹配、补卡永远不生效。
    for req in qs:
        if req.miss_type in ("sign_in", "in"):
            covered["in"] = True
        elif req.miss_type in ("sign_out", "out"):
            covered["out"] = True
    return covered


def _approved_overtime_minutes(user: User, date) -> int:
    from apps.workflow.models import OvertimeRequest

    total = 0
    qs = OvertimeRequest.objects.filter(
        applicant=user, status=OvertimeRequest.Status.APPROVED, is_deleted=False,
        start_at__lte=make_aware(date, time(23, 59, 59)),
        end_at__gte=make_aware(date, time(0, 0)),
    )
    for req in qs:
        if req.start_at and req.end_at:
            start = max(timezone.localtime(req.start_at), make_aware(date, time(0, 0)))
            end = min(timezone.localtime(req.end_at), make_aware(date, time(23, 59, 59)))
            total += max(0, int((end - start).total_seconds() // 60))
    return total


# ---------------------------------------------------------------- 日报重算
def _classify_day(user: User, date, rule: AttendanceRule | None):
    """返回 (additional_status, extra) —— 节假日/出差/请假优先于打卡结果。"""
    holiday = AttendanceHoliday.objects.filter(date=date, is_deleted=False).first()
    if holiday:
        if holiday.type == AttendanceHoliday.Type.WORKDAY:
            pass  # 调休上班日，按正常工作日处理
        else:
            return AttendanceDaily.Status.HOLIDAY, holiday.name

    weekday = date.isoweekday()
    if weekday not in (rule.effective_workdays if rule else DEFAULT_WORKDAYS):
        return AttendanceDaily.Status.REST, "非工作日"

    if _has_approved(user, date, _trip_model()):
        return AttendanceDaily.Status.TRIP, "出差"
    if _approved_leave_days(user, date) > 0:
        return AttendanceDaily.Status.LEAVE, "请假"
    return None, ""


def _trip_model():
    from apps.workflow.models import TripRequest

    return TripRequest


def rebuild_daily(user: User, date, manual=False) -> AttendanceDaily:
    """重算单个员工某天的考勤日报，并同步生成/关闭异常记录。

    Args:
        user: 员工。
        date: 目标日期（date 对象或可解析字符串）。
        manual: 是否人工修正（保留标记，供审计区分）。

    Returns:
        重算后的 AttendanceDaily。
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    rule = get_rule_for_user(user)
    punch_date_qs = PunchRecord.objects.filter(user=user, punch_date=date, is_deleted=False).order_by("punch_at")
    punches = list(punch_date_qs)
    sign_in = punches[0].punch_at if punches else None
    sign_out = punches[-1].punch_at if len(punches) > 1 else None

    pre_status, remark = _classify_day(user, date, rule)
    covered = _approved_cardifies(user, date)

    late_minutes = early_minutes = overtime_minutes = 0
    work_minutes = 0
    status = pre_status or AttendanceDaily.Status.NORMAL

    if status == AttendanceDaily.Status.NORMAL:
        if rule is None:
            status = AttendanceDaily.Status.MISS
            remark = "未配置考勤规则"
        elif not punches:
            status = AttendanceDaily.Status.ABSENT
            remark = "当日无打卡记录"
        else:
            start_dt = make_aware(date, rule.work_start)
            end_dt = make_aware(date, rule.work_end)

            if sign_in > start_dt + timedelta(minutes=rule.late_minutes):
                late_minutes = int((sign_in - start_dt).total_seconds() // 60)
                status = AttendanceDaily.Status.LATE
                remark = f"迟到 {late_minutes} 分钟"

            if sign_out is None:
                if not covered.get("out"):
                    status = AttendanceDaily.Status.MISS
                    remark = "缺少下班卡"
            else:
                if sign_out < end_dt - timedelta(minutes=rule.early_leave_minutes):
                    early_minutes = int((end_dt - sign_out).total_seconds() // 60)
                    if status == AttendanceDaily.Status.NORMAL:
                        status = AttendanceDaily.Status.EARLY_LEAVE
                    remark = (remark + "；" if remark else "") + f"早退 {early_minutes} 分钟"
                beyond = int((sign_out - end_dt).total_seconds() // 60)
                if beyond >= (rule.overtime_min_minutes or 60):
                    overtime_minutes = beyond

            work_minutes = 0
            if sign_in and sign_out:
                work_minutes = max(0, int((sign_out - sign_in).total_seconds() // 60))

            # 迟到/早退累计超过阈值 → 旷工
            if late_minutes + early_minutes >= rule.absent_minutes:
                status = AttendanceDaily.Status.ABSENT
                remark = f"迟到/早退累计 {late_minutes + early_minutes} 分钟，判定旷工"

    overtime_minutes = max(overtime_minutes, _approved_overtime_minutes(user, date))

    daily, _ = AttendanceDaily.all_objects.get_or_create(
        user=user, date=date,
        defaults={"created_by": user},
    )
    daily.rule = rule
    daily.sign_in_at = sign_in
    daily.sign_out_at = sign_out
    daily.work_minutes = work_minutes
    daily.late_minutes = late_minutes
    daily.early_minutes = early_minutes
    daily.overtime_minutes = overtime_minutes
    daily.status = status
    daily.punch_count = len(punches)
    daily.remark = remark
    daily.source = "manual" if manual else daily.source
    daily.is_deleted = False
    daily.save()

    _sync_exceptions(daily, covered)
    return daily


def _sync_exceptions(daily: AttendanceDaily, covered: dict) -> None:
    """依据日报状态生成异常记录；已人工处理的记录不被覆盖。"""
    wanted: list = []
    if daily.status == AttendanceDaily.Status.LATE:
        wanted.append((AttendanceException.Type.LATE, daily.late_minutes, "迟到"))
    elif daily.status == AttendanceDaily.Status.EARLY_LEAVE:
        wanted.append((AttendanceException.Type.EARLY_LEAVE, daily.early_minutes, "早退"))
    elif daily.status == AttendanceDaily.Status.MISS:
        if daily.sign_in_at is None and not covered.get("in"):
            wanted.append((AttendanceException.Type.MISS_IN, 0, "缺少上班卡"))
        elif daily.sign_out_at is None and not covered.get("out"):
            wanted.append((AttendanceException.Type.MISS_OUT, 0, "缺少下班卡"))
    elif daily.status == AttendanceDaily.Status.ABSENT:
        wanted.append((AttendanceException.Type.ABSENT, 0, daily.remark or "当日无打卡"))

    existing = {
        e.type: e
        for e in AttendanceException.objects.filter(user=daily.user, date=daily.date)
    }
    keep = set()
    for etype, minutes, reason in wanted:
        keep.add(etype)
        obj = existing.get(etype)
        if obj is None:
            AttendanceException.objects.create(
                user=daily.user, date=daily.date, type=etype, minutes=minutes, reason=reason,
            )
        elif obj.status == AttendanceException.Status.PENDING:
            # 仅刷新尚未处理的记录，避免覆盖人工判定结果
            obj.minutes = minutes
            obj.reason = reason
            obj.save(update_fields=["minutes", "reason", "updated_at"])

    for etype, obj in existing.items():
        if etype in keep:
            continue
        if obj.status == AttendanceException.Status.PENDING:
            # 异常已消失（例如补卡通过），自动关闭
            obj.status = AttendanceException.Status.IGNORED
            obj.handle_result = "系统自动关闭：异常已消除"
            obj.save(update_fields=["status", "handle_result", "updated_at"])


def rebuild_range(start_date, end_date, users=None) -> int:
    """批量重建区间的考勤日报。返回处理的人日数。"""
    qs = User.objects.filter(is_active=True, status=User.Status.ACTIVE)
    if users:
        qs = qs.filter(id__in=[u.id if isinstance(u, User) else u for u in users])
    count = 0
    day = start_date
    while day <= end_date:
        for user in qs:
            rebuild_daily(user, day)
            count += 1
        day += timedelta(days=1)
    return count


# ---------------------------------------------------------------- 月度汇总
@transaction.atomic
def month_summary(user: User, month: str, rebuild=False) -> AttendanceSummary:
    """生成（或读取）某员工的月度汇总。

    Args:
        user: 员工。
        month: "YYYY-MM"。
        rebuild: 为 True 时先重算该月每日日报。
    """
    year, mon = int(month[:4]), int(month[5:7])
    start = datetime(year, mon, 1).date()
    end = (datetime(year + (mon == 12), (mon % 12) + 1, 1) - timedelta(days=1)).date()

    if rebuild:
        rebuild_range(start, end, [user])

    rows = AttendanceDaily.objects.filter(user=user, date__gte=start, date__lte=end)
    agg = rows.aggregate(
        work_minutes=Sum("work_minutes"),
        overtime_minutes=Sum("overtime_minutes"),
    )
    by_status = {row["status"]: row["c"] for row in rows.values("status").annotate(c=Count("id"))}
    work_days = (end - start).days + 1

    present_days = by_status.get(AttendanceDaily.Status.NORMAL, 0)
    present_days += by_status.get(AttendanceDaily.Status.LATE, 0)
    present_days += by_status.get(AttendanceDaily.Status.EARLY_LEAVE, 0)

    summary, _ = AttendanceSummary.objects.get_or_create(user=user, month=month)
    summary.work_days = max(0, work_days - by_status.get(AttendanceDaily.Status.REST, 0)
                            - by_status.get(AttendanceDaily.Status.HOLIDAY, 0))
    summary.present_days = present_days
    summary.late_count = by_status.get(AttendanceDaily.Status.LATE, 0)
    summary.early_count = by_status.get(AttendanceDaily.Status.EARLY_LEAVE, 0)
    summary.absent_count = by_status.get(AttendanceDaily.Status.ABSENT, 0)
    summary.miss_count = by_status.get(AttendanceDaily.Status.MISS, 0)
    summary.leave_days = Decimal(by_status.get(AttendanceDaily.Status.LEAVE, 0))
    summary.work_minutes = agg["work_minutes"] or 0
    summary.overtime_minutes = agg["overtime_minutes"] or 0
    summary.attendance_rate = (
        Decimal(summary.present_days) / Decimal(summary.work_days) * 100
        if summary.work_days else Decimal("0")
    )
    summary.save()
    return summary


def dept_summary(month: str, dept_id: int | None = None) -> list:
    """部门维度的考勤汇总报表。"""
    dept = Department.objects.filter(id=dept_id).first() if dept_id else None
    users = User.objects.filter(is_active=True)
    if dept:
        ids = dept.descendant_ids()
        users = users.filter(dept_id__in=ids)
    result = []
    for user in users.select_related("dept").order_by("dept__name", "id"):
        summary = month_summary(user, month)
        result.append(
            {
                "user_id": user.id,
                "username": user.username,
                "name": user.display_name,
                "employee_no": user.employee_no,
                "dept": user.dept.name if user.dept else "",
                **{
                    k: getattr(summary, k)
                    for k in (
                        "work_days", "present_days", "late_count", "early_count",
                        "absent_count", "miss_count", "leave_days", "work_minutes",
                        "overtime_minutes", "attendance_rate",
                    )
                },
            }
        )
    return result


# ---------------------------------------------------------------- 异常处理
def handle_exception(exception_id: int, handler: User, result: str, status: str = "handled") -> AttendanceException:
    """处理考勤异常，并回写日报状态（补卡成立时消除缺卡）。"""
    exc = AttendanceException.objects.filter(id=exception_id).first()
    if exc is None:
        raise BusinessException("考勤异常记录不存在", code=4040, status_code=404)
    if exc.status == AttendanceException.Status.HANDLED:
        raise BusinessException("该异常已处理", code=4002)

    exc.status = AttendanceException.Status.HANDLED if status != "ignored" else AttendanceException.Status.IGNORED
    exc.handler = handler
    exc.handle_result = result
    exc.handled_at = timezone.now()
    exc.save()

    # 忽略类处理 → 修正日报状态为正常，避免重复出现在异常列表（人为豁免）
    if exc.status == AttendanceException.Status.HANDLED and exc.type in (
        AttendanceException.Type.LATE, AttendanceException.Type.EARLY_LEAVE,
    ):
        daily = AttendanceDaily.objects.filter(user=exc.user, date=exc.date).first()
        if daily and daily.status != AttendanceDaily.Status.MISS:
            daily.status = AttendanceDaily.Status.NORMAL
            daily.remark = f"异常已处理：{result}"
            daily.save(update_fields=["status", "remark", "updated_at"])

    notify_user(exc.user, "考勤异常已处理", f"{exc.date} {exc.get_type_display()}：{result}",
                biz_type="attendance", biz_id=exc.id)
    return exc


def daily_queryset_for_user(user: User, params: dict):
    """按查询条件过滤日报，兼顾数据范围控制。"""
    qs = AttendanceDaily.objects.select_related("user", "rule").filter(is_deleted=False)
    start = params.get("start_date")
    end = params.get("end_date")
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    if params.get("user_id"):
        qs = qs.filter(user_id=params["user_id"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("dept_id"):
        dept = Department.objects.filter(id=params["dept_id"]).first()
        if dept:
            qs = qs.filter(user__dept_id__in=dept.descendant_ids())
    if params.get("keyword"):
        kw = params["keyword"]
        qs = qs.filter(Q(user__username__icontains=kw) | Q(user__first_name__icontains=kw)
                       | Q(user__employee_no__icontains=kw))
    return qs.order_by("-date", "id")


def export_rows(queryset) -> list:
    """把日报查询集转换为导出用的二维数组行。"""
    header = ["工号", "姓名", "部门", "日期", "状态", "上班打卡", "下班打卡",
              "工时(分钟)", "迟到(分钟)", "早退(分钟)", "加班(分钟)", "备注"]
    rows = [header]
    for d in queryset:
        rows.append(
            [
                d.user.employee_no or "", d.user.display_name,
                d.user.dept.name if d.user.dept else "", str(d.date),
                d.get_status_display(),
                timezone.localtime(d.sign_in_at).strftime("%H:%M") if d.sign_in_at else "",
                timezone.localtime(d.sign_out_at).strftime("%H:%M") if d.sign_out_at else "",
                d.work_minutes, d.late_minutes, d.early_minutes, d.overtime_minutes, d.remark,
            ]
        )
    return rows
