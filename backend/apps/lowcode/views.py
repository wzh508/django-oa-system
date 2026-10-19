"""低代码接口。"""
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet, BaseViewSet

from .models import DynamicRecord, FormSchema
from .serializers import (
    DynamicRecordSerializer,
    DynamicRecordWriteSerializer,
    FormSchemaSerializer,
    FormSchemaWriteSerializer,
)


class FormSchemaViewSet(BaseModelViewSet):
    """动态表单 schema 管理 + 渲染接口。"""

    queryset = FormSchema.objects.all()
    perm_prefix = "lowcode"
    audit_module = "lowcode"
    perm_map = {
        "create": "lowcode:form:create",
        "update": "lowcode:form:update",
        "partial_update": "lowcode:form:update",
        "destroy": "lowcode:form:destroy",
        "publish": "lowcode:form:update",
        "render": "lowcode:form:list",
    }

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FormSchemaWriteSerializer
        return FormSchemaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("code"):
            qs = qs.filter(code=p.get("code"))
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("only_published") == "1":
            qs = qs.filter(status=FormSchema.Status.PUBLISHED)
        return qs.order_by("code", "-version")

    @extend_schema(summary="发布表单（设为当前生效版本）")
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        with transaction.atomic():
            schema = FormSchema.objects.select_for_update().get(id=pk)
            if not schema.fields:
                from apps.common.exceptions import BusinessException

                raise BusinessException("表单未配置字段，无法发布", code=4001)
            FormSchema.objects.filter(code=schema.code, status=FormSchema.Status.PUBLISHED).exclude(
                id=schema.id).update(status=FormSchema.Status.DRAFT)
            schema.status = FormSchema.Status.PUBLISHED
            schema.save(update_fields=["status"])
        return ok(FormSchemaSerializer(schema).data)

    @extend_schema(summary="按编码获取已发布表单用于前端渲染")
    @action(detail=False, methods=["get"], url_path="render")
    def render(self, request):
        code = request.query_params.get("code")
        if not code:
            from apps.common.exceptions import BusinessException

            raise BusinessException("缺少 code 参数", code=4001)
        schema = FormSchema.objects.filter(code=code, status=FormSchema.Status.PUBLISHED).order_by(
            "-version").first()
        if schema is None:
            from apps.common.exceptions import BusinessException

            raise BusinessException("未找到已发布表单", code=4040, status_code=404)
        return ok(FormSchemaSerializer(schema).data)


class DynamicRecordViewSet(BaseModelViewSet):
    """动态数据提交与查询（任何登录用户均可提交、查看本人数据）。"""

    queryset = DynamicRecord.objects.all().select_related("form", "submitter")
    perm_prefix = "lowcode"
    audit_module = "lowcode"
    open_actions = {"create", "list", "retrieve"}
    perm_map = {"update": "lowcode:form:update", "destroy": "lowcode:form:destroy",
                "process": "lowcode:form:update"}

    def get_serializer_class(self):
        if self.action == "create":
            return DynamicRecordWriteSerializer
        return DynamicRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        p = self.request.query_params
        if not user.is_superuser and self.action == "list":
            qs = qs.filter(submitter=user)
        if p.get("form_code"):
            qs = qs.filter(form_code=p.get("form_code"))
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        return qs.order_by("-id")

    def perform_create(self, serializer):
        form = serializer.validated_data["form"]
        serializer.save(submitter=self.request.user, form_code=form.code, created_by=self.request.user)

    @extend_schema(summary="处理动态数据（标记完成/归档）")
    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        rec = self.get_object()
        status = (request.data or {}).get("status", DynamicRecord.Status.DONE)
        rec.status = status
        rec.save(update_fields=["status"])
        return ok(DynamicRecordSerializer(rec).data)
