"""低代码序列化器。"""
from rest_framework import serializers

from .models import DynamicRecord, FormSchema


class FormSchemaWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSchema
        fields = ["id", "code", "name", "description", "category", "version", "status", "fields"]


class FormSchemaSerializer(serializers.ModelSerializer):
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = FormSchema
        fields = ["id", "code", "name", "description", "category", "version", "status",
                  "fields", "field_count", "created_at", "updated_at"]

    def get_field_count(self, obj) -> int:
        return len(obj.fields or [])


class DynamicRecordSerializer(serializers.ModelSerializer):
    submitter_name = serializers.CharField(source="submitter.display_name", read_only=True, default="")
    form_name = serializers.CharField(source="form.name", read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DynamicRecord
        fields = ["id", "form", "form_code", "form_name", "form_data", "submitter",
                  "submitter_name", "status", "status_display", "created_at", "updated_at"]
        read_only_fields = ["submitter", "form_code", "form_name"]


class DynamicRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicRecord
        fields = ["id", "form", "form_data"]

    def validate(self, attrs):
        form = attrs.get("form")
        if form is None or form.status != FormSchema.Status.PUBLISHED:
            raise serializers.ValidationError("表单不存在或未发布")
        data = attrs.get("form_data") or {}
        for f in (form.fields or []):
            if f.get("required") and not data.get(f.get("key")):
                raise serializers.ValidationError(f"必填项缺失：{f.get('label')}")
        return attrs
