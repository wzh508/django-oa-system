"""文档中心域接口。"""
import os
import uuid

from django.conf import settings
from django.db.models import F
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from apps.common.exceptions import BusinessException
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet

from .models import Document
from .serializers import DocumentSerializer


def _media_root() -> str:
    base = getattr(settings, "MEDIA_ROOT", None) or os.path.join(settings.BASE_DIR, "media")
    return os.path.join(base, "documents")


def _category_by_ext(name: str) -> str:
    ext = os.path.splitext(name)[-1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"):
        return Document.Category.IMAGE
    if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return Document.Category.VIDEO
    return Document.Category.DOC if ext else Document.Category.OTHER


class DocumentViewSet(BaseModelViewSet):
    """文档中心：文件夹、上传、下载、共享。"""

    queryset = Document.objects.all().select_related("owner", "dept", "parent")
    perm_prefix = "document"
    audit_module = "document"
    serializer_class = DocumentSerializer
    perm_map = {"create": "document:upload"}

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("parent") is not None:
            pid = p.get("parent")
            qs = qs.filter(parent_id=pid if pid else None)
        if p.get("is_folder"):
            qs = qs.filter(is_folder=(p.get("is_folder") == "1"))
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("share_type"):
            qs = qs.filter(share_type=p.get("share_type"))
        if p.get("keyword"):
            qs = qs.filter(name__icontains=p.get("keyword"))
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(summary="上传文件", description="multipart/form-data：file + name + parent + share_type")
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        f = request.FILES.get("file")
        if not f:
            raise BusinessException("缺少文件", code=4001)
        parent_id = request.data.get("parent") or None
        name = request.data.get("name") or f.name
        share_type = request.data.get("share_type") or Document.ShareType.PRIVATE
        if share_type not in Document.ShareType.values:
            raise BusinessException("共享范围非法", code=4001)
        root = _media_root()
        rel = f"{timezone.now().strftime('%Y%m')}/{uuid.uuid4().hex}_{f.name}"
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        doc = Document.objects.create(
            name=name, parent_id=parent_id, is_folder=False, owner=request.user,
            original_name=f.name, file=rel, mime=f.content_type or "", size=f.size,
            category=_category_by_ext(f.name), share_type=share_type,
            description=request.data.get("description", "") or "",
        )
        return ok(DocumentSerializer(doc, context={"request": request}).data)

    @extend_schema(summary="下载文件", description="返回文件流并计数 +1")
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        doc = self.get_object()
        if doc.is_folder or not doc.file:
            raise BusinessException("该记录不可下载", code=4001)
        full = os.path.join(_media_root(), doc.file)
        if not os.path.exists(full):
            raise Http404("文件不存在")
        Document.objects.filter(id=doc.id).update(download_count=F("download_count") + 1)
        return FileResponse(open(full, "rb"), as_attachment=True, filename=doc.original_name or doc.name)

    @extend_schema(summary="设置共享范围")
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        doc = self.get_object()
        share_type = (request.data or {}).get("share_type")
        if share_type not in Document.ShareType.values:
            raise BusinessException("共享范围非法", code=4001)
        doc.share_type = share_type
        doc.save(update_fields=["share_type"])
        return ok({"id": doc.id, "share_type": doc.share_type})
