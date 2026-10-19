"""考勤域序列化器。"""
from rest_framework import serializers

from apps.accounts.serializers import UserListSerializer

from .models import (
    AttendanceDaily,
    AttendanceException,
    AttendanceHoliday,
    AttendanceRule,
    AttendanceSummary,
    PunchRecord,
)


class AttendanceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRule
        fields = ["id", "name", "code", "work_start", "work_end", "work_minutes", "late_minutes",
                  "early_leave_minutes", "absent_minutes", "overtime_min_minutes", "workdays",
                  "dept_ids", "is_default", "enabled", "remark", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if attrs.get("work_start") and attrs.get("work_end") and attrs["work_start"] >= attrs["work_end"]:
            raise serializers.ValidationError("上班时间必须早于下班时间")
        return attrs


class AttendanceHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceHoliday
        fields = ["id", "date", "name", "type", "remark"]
        read_only_fields = ["id"]


class PunchRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PunchRecord
        fields = ["id", "user", "punch_at", "punch_date", "punch_type", "source", "location", "device", "remark"]
        read_only_fields = ["id", "punch_date"]


class PunchCreateSerializer(serializers.Serializer):
    punch_at = serializers.DateTimeField(required=False, allow_null=True)
    punch_type = serializers.ChoiceField(choices=PunchRecord.PunchType.choices, required=False, default="auto")
    source = serializers.ChoiceField(choices=PunchRecord.Source.choices, required=False, default="web")
    location = serializers.CharField(required=False, allow_blank=True, default="")
    device = serializers.CharField(required=False, allow_blank=True, default="")
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class AttendanceDailySerializer(serializers.ModelSerializer):
    user = UserListSerializer(read_only=True)
    user__id = serializers.IntegerField(source="user.id", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    dept_name = serializers.CharField(source="user.dept.name", read_only=True, default="")
    rule_name = serializers.CharField(source="rule.name", read_only=True, default="")

    class Meta:
        model = AttendanceDaily
        fields = ["id", "user", "user__id", "dept_name", "date", "rule", "rule_name", "sign_in_at",
                  "sign_out_at", "work_minutes", "late_minutes", "early_minutes", "overtime_minutes",
                  "status", "status_display", "punch_count", "source", "remark"]


class DailyAdjustSerializer(serializers.Serializer):
    date = serializers.DateField()
    user_id = serializers.IntegerField()
    sign_in_at = serializers.DateTimeField(required=False, allow_null=True)
    sign_out_at = serializers.DateTimeField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=AttendanceDaily.Status.choices, required=False)


class AttendanceExceptionSerializer(serializers.ModelSerializer):
    user = UserListSerializer(read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    dept_name = serializers.CharField(source="user.dept.name", read_only=True, default="")

    class Meta:
        model = AttendanceException
        fields = ["id", "user", "dept_name", "date", "type", "type_display", "minutes", "status",
                  "status_display", "reason", "handler", "handle_result", "handled_at", "created_at"]


class ExceptionHandleSerializer(serializers.Serializer):
    result = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=["handled", "ignored"], required=False, default="handled")


class AttendanceSummarySerializer(serializers.ModelSerializer):
    user = UserListSerializer(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)
    leave_days = serializers.FloatField(read_only=True)

    class Meta:
        model = AttendanceSummary
        fields = ["id", "user", "month", "work_days", "present_days", "late_count", "early_count",
                  "absent_count", "miss_count", "leave_days", "work_minutes", "overtime_minutes",
                  "attendance_rate"]
