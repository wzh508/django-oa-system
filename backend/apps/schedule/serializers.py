"""日程与任务域序列化器。"""
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from .models import Schedule, Task


class ScheduleSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.first_name", read_only=True, default="")
    participant_ids = serializers.ListField(child=serializers.IntegerField(), required=False,
                                            write_only=True, default=list)
    participant_names = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = ["id", "title", "content", "owner", "owner_name", "participant_ids",
                  "participant_names", "start", "end", "all_day", "location", "category",
                  "remind_before", "status", "created_at"]
        read_only_fields = ["owner_name", "participant_names", "created_at"]

    def get_participant_names(self, obj) -> list:
        return [u.first_name or u.username for u in obj.participants.all()]

    def create(self, validated_data):
        ids = validated_data.pop("participant_ids", [])
        obj = super().create(validated_data)
        if ids:
            obj.participants.set(ids)
        return obj

    def update(self, instance, validated_data):
        ids = validated_data.pop("participant_ids", None)
        instance = super().update(instance, validated_data)
        if ids is not None:
            instance.participants.set(ids)
        return instance


# 与 apps.workflow.serializers.TaskSerializer 同名，需显式区分 OpenAPI 组件名，否则 schema 生成冲突
@extend_schema_serializer(component_name="ScheduleTask")
class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.first_name", read_only=True, default="")

    class Meta:
        model = Task
        fields = ["id", "title", "content", "assignee", "assignee_name", "creator", "start",
                  "due", "status", "priority", "progress", "parent", "tags", "created_at"]
        read_only_fields = ["assignee_name", "creator", "created_at"]
