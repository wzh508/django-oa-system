"""站内消息接口。"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet

from .models import Message
from .serializers import MessageSerializer


class MessageViewSet(BaseModelViewSet):
    """消息中心：仅本人收件箱，支持标记已读。"""

    serializer_class = MessageSerializer
    perm_prefix = "message"
    audit_module = "message"
    open_actions = {"list", "read", "read_all", "unread_count"}
    perm_map = {"read": "message:read", "read_all": "message:read"}

    def get_queryset(self):
        qs = Message.objects.filter(recipient=self.request.user)
        p = self.request.query_params
        if p.get("unread") == "1":
            qs = qs.filter(is_read=False)
        if p.get("biz_type"):
            qs = qs.filter(biz_type=p.get("biz_type"))
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(recipient=self.request.user, created_by=self.request.user)

    @extend_schema(summary="标记已读")
    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        msg = self.get_object()
        if not msg.is_read:
            msg.is_read = True
            msg.read_at = timezone.now()
            msg.save(update_fields=["is_read", "read_at"])
        return ok(MessageSerializer(msg).data)

    @extend_schema(summary="全部标记已读")
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        n = self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return ok({"updated": n})

    @extend_schema(summary="未读数量")
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return ok({"count": self.get_queryset().filter(is_read=False).count()})
