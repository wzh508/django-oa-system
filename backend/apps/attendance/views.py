"""考勤接口。

权限码通过 perm_prefix 自动推导，特殊 action 用 perm_map 显式映射。
"""
import logging
from datetime import datetime, timedelta
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.accounts.services import get_data_scope_q
from apps.common.exceptions import BusinessException
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet, BaseViewSet

from . import services
from .models import (
    AttendanceDaily,
    AttendanceException,
    AttendanceHoliday,
    AttendanceRule,
    AttendanceSummary,
    PunchRecord,
)
from .serializers import (
    AttendanceDailySerializer,
    AttendanceExceptionSerializer,
    AttendanceHolidaySerializer,
    AttendanceRuleSerializer,
    AttendanceSummarySerializer,
    DailyAdjustSerializer,
    ExceptionHandleSerializer,
    PunchCreateSerializer,
    PunchRecordSerializer,
)

logger = logging.getLogger(__name__)


class AttendanceRuleViewSet(BaseModelViewSet):
    """考勤规则管理（班次、节假日日历）。"""

    queryset = AttendanceRule.objects.all()
    serializer_class = AttendanceRuleSerializer
    perm_prefix = "attendance:rule"
    perm_map = {"retrieve": "attendance:rule:list"}
    audit_module = "attendance"

    @extend_schema(summary="节假日日历", parameters=[])
    @action(detail=False, methods=["get"], url_path="holidays")
    def holidays(self, request):
        year = request.query_params.get("year") or timezone.localdate().year
        rows = AttendanceHoliday.objects.filter(date__year=int(year))
        return ok(AttendanceHolidaySerializer(rows, many=True).data)

    @extend_schema(summary="新增/更新节假日")
    @action(detail=False, methods=["post"], url_path="holidays/save")
    def holidays_save(self, request):
        serializer = AttendanceHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        date = serializer.validated_data["date"]
        obj, _ = AttendanceHoliday.all_objects.get_or_create(
            date=date, defaults={"created_by": request.user}
        )
        for field, value in serializer.validated_data.items():
            setattr(obj, field, value)
        obj.is_deleted = False
        obj.save()
        return ok(AttendanceHolidaySerializer(obj).data)


class PunchViewSet(BaseViewSet):
    """打卡。"""

    perm_prefix = "attendance:punch"
    perm_map = {"create": "attendance:punch:create", "list": "attendance:punch:list",
                "today": "attendance:punch:list"}
    audit_module = "attendance"

    def get_serializer_class(self):
        return PunchCreateSerializer if self.action == "create" else PunchRecordSerializer

    def get_queryset(self):
        qs = PunchRecord.objects.filter(user=self.request.user)
        month = self.request.query_params.get("month")
        if month:
            qs = qs.filter(punch_date__startswith=month)
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            qs = qs.filter(punch_date__gte=start)
        if end:
            qs = qs.filter(punch_date__lte=end)
        return qs.order_by("-punch_at")

    @extend_schema(summary="打卡（上下班）", request=PunchCreateSerializer, responses=PunchRecordSerializer)
    def create(self, request):
        serializer = PunchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = services.punch(request.user, **serializer.validated_data)
        return ok(PunchRecordSerializer(record).data)

    @extend_schema(summary="今日打卡概况")
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        today = timezone.localdate()
        daily = AttendanceDaily.objects.filter(user=request.user, date=today).first()
        if daily is None:
            daily = services.rebuild_daily(request.user, today)
        punches = PunchRecord.objects.filter(user=request.user, punch_date=today).order_by("punch_at")
        rule = services.get_rule_for_user(request.user)
        return ok(
            {
                "date": str(today),
                "rule": AttendanceRuleSerializer(rule).data if rule else None,
                "daily": AttendanceDailySerializer(daily).data,
                "punches": PunchRecordSerializer(punches, many=True).data,
            }
        )


class AttendanceRecordViewSet(BaseModelViewSet):
    """考勤日报。"""

    queryset = AttendanceDaily.objects.select_related("user", "rule").filter(is_deleted=False)
    serializer_class = AttendanceDailySerializer
    perm_prefix = "attendance:record"
    perm_map = {"retrieve": "attendance:record:list", "export": "attendance:record:export",
                "rebuild": "attendance:record:rebuild", "adjust": "attendance:record:rebuild"}
    audit_module = "attendance"
    filterset_fields: list = []
    search_fields = ["user__username", "user__first_name", "user__employee_no"]
    ordering_fields = ["date", "created_at"]
    #: 数据范围资源标识；未配置规则时回退「仅本人」，避免越权查看他人考勤
    data_scope_resource = "attendance.record"
    #: 该资源按考勤归属人（user）而非创建人判定归属
    data_scope_user_field = "user"

    def get_queryset(self):
        qs = services.daily_queryset_for_user(self.request.user, self.request.query_params)
        # 超管返回 None；其余用户按角色数据范围（SELF/DEPT_TREE/ALL…）收窄
        q = get_data_scope_q(self.request.user, self.data_scope_resource,
                             user_field=self.data_scope_user_field)
        if q is not None:
            qs = qs.filter(q)
        return qs

    @extend_schema(summary="重算考勤日报", description="按 start_date / end_date / user_id 触发重算")
    @action(detail=False, methods=["post"], url_path="rebuild")
    def rebuild(self, request):
        p = request.data or {}
        end = p.get("end_date") or timezone.localdate().isoformat()
        start = p.get("start_date") or (timezone.localdate() - timedelta(days=30)).isoformat()
        users = None
        if p.get("user_id"):
            users = [p["user_id"]]
        count = services.rebuild_range(
            datetime.strptime(str(start)[:10], "%Y-%m-%d").date(),
            datetime.strptime(str(end)[:10], "%Y-%m-%d").date(),
            users,
        )
        return ok({"rebuilt": count})

    @extend_schema(summary="人工修正考勤结果", request=DailyAdjustSerializer)
    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request):
        serializer = DailyAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from apps.accounts.models import User

        user = User.objects.filter(id=data["user_id"]).first()
        if user is None:
            raise BusinessException("用户不存在", code=4040, status_code=404)
        daily = AttendanceDaily.all_objects.get_or_create(
            user=user, date=data["date"], defaults={"created_by": request.user}
        )[0]
        if "sign_in_at" in data:
            daily.sign_in_at = data["sign_in_at"]
        if "sign_out_at" in data:
            daily.sign_out_at = data["sign_out_at"]
        if data.get("status"):
            daily.status = data["status"]
        daily.remark = data.get("remark", "")
        daily.source = "manual"
        daily.is_deleted = False
        daily.save()
        return ok(AttendanceDailySerializer(daily).data)

    @extend_schema(summary="导出考勤报表（JSON 行数据，前端可转 CSV/Excel）")
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.get_queryset()
        rows = services.export_rows(qs[:5000])
        if request.query_params.get("format") == "csv":
            import csv

            buf = BytesIO()
            writer = csv.writer(buf)
            writer.writerow(["\ufeff" + rows[0][0]] + rows[0][1:])
            writer.writerows(rows[1:])
            resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
            resp["Content-Disposition"] = 'attachment; filename="attendance.csv"'
            return resp
        return ok({"total": len(rows) - 1, "rows": rows})


class AttendanceExceptionViewSet(BaseModelViewSet):
    """考勤异常处理。"""

    queryset = AttendanceException.objects.select_related("user").filter(is_deleted=False)
    serializer_class = AttendanceExceptionSerializer
    perm_prefix = "attendance:exception"
    perm_map = {"retrieve": "attendance:exception:list", "handle": "attendance:exception:handle"}
    audit_module = "attendance"
    search_fields = ["user__username", "user__first_name"]
    data_scope_resource = "attendance.exception"
    data_scope_user_field = "user"

    def get_queryset(self):
        qs = super().get_queryset()
        q = get_data_scope_q(self.request.user, self.data_scope_resource,
                             user_field=self.data_scope_user_field)
        if q is not None:
            qs = qs.filter(q)
        p = self.request.query_params
        if p.get("date_start"):
            qs = qs.filter(date__gte=p["date_start"])
        if p.get("date_end"):
            qs = qs.filter(date__lte=p["date_end"])
        if p.get("type"):
            qs = qs.filter(type=p["type"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("dept_id"):
            from apps.accounts.models import Department

            dept = Department.objects.filter(id=p["dept_id"]).first()
            if dept:
                qs = qs.filter(user__dept_id__in=dept.descendant_ids())
        return qs.order_by("-date", "id")

    @extend_schema(summary="处理考勤异常", request=ExceptionHandleSerializer)
    @action(detail=True, methods=["post"], url_path="handle")
    def handle(self, request, pk=None):
        serializer = ExceptionHandleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exc = services.handle_exception(
            int(pk), request.user, serializer.validated_data["result"], serializer.validated_data["status"]
        )
        return ok(AttendanceExceptionSerializer(exc).data)


class AttendanceSummaryViewSet(BaseViewSet):
    """考勤汇总报表。"""

    perm_prefix = "attendance:summary"
    perm_map = {"dept": "attendance:summary:dept", "monthly": "attendance:summary:monthly"}
    audit_module = "attendance"
    serializer_class = AttendanceSummarySerializer

    @extend_schema(summary="部门月度考勤汇总")
    @action(detail=False, methods=["get"], url_path="dept")
    def dept(self, request):
        month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
        dept_id = request.query_params.get("dept_id")
        rows = services.dept_summary(month, int(dept_id) if dept_id else None)
        return ok({"month": month, "total": len(rows), "rows": rows})

    @extend_schema(summary="个人月度汇总（不存在则自动计算）")
    @action(detail=False, methods=["get"], url_path="monthly")
    def monthly(self, request):
        month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
        user = request.user
        if request.query_params.get("user_id"):
            from apps.accounts.models import User

            user = User.objects.filter(id=request.query_params["user_id"]).first() or request.user
        summary = services.month_summary(user, month)
        return ok(AttendanceSummarySerializer(summary).data)
