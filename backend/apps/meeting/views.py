"""会议域接口。"""
import os

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from apps.common.exceptions import BusinessException
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet

from .models import MeetingBooking, MeetingMinute, MeetingRoom
from .serializers import BookingSerializer, MeetingRoomSerializer, MinuteSerializer


def _minute_media_root() -> str:
    base = getattr(settings, "MEDIA_ROOT", None) or os.path.join(settings.BASE_DIR, "media")
    return os.path.join(base, "minutes")


class MeetingRoomViewSet(BaseModelViewSet):
    """会议室维护。"""
    queryset = MeetingRoom.objects.all()
    perm_prefix = "meeting:room"
    audit_module = "meeting"
    serializer_class = MeetingRoomSerializer


class BookingViewSet(BaseModelViewSet):
    """会议预约，含时间段冲突检测与取消。"""
    queryset = MeetingBooking.objects.all().select_related("room", "organizer").prefetch_related("attendees")
    perm_prefix = "meeting:booking"
    audit_module = "meeting"
    serializer_class = BookingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("room_id"):
            qs = qs.filter(room_id=p.get("room_id"))
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("from"):
            qs = qs.filter(start__gte=p.get("from"))
        if p.get("to"):
            qs = qs.filter(end__lte=p.get("to"))
        return qs

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    @extend_schema(summary="取消预约")
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        b = self.get_object()
        if b.status == MeetingBooking.Status.CANCELLED:
            raise BusinessException("预约已取消", code=4002)
        b.status = MeetingBooking.Status.CANCELLED
        b.save(update_fields=["status"])
        return ok({"id": b.id, "status": b.status})


class MinuteViewSet(BaseModelViewSet):
    """会议纪要，支持附件上传。"""
    queryset = MeetingMinute.objects.all().select_related("booking", "uploader")
    perm_prefix = "meeting:minute"
    audit_module = "meeting"
    serializer_class = MinuteSerializer

    def perform_create(self, serializer):
        serializer.save(uploader=self.request.user)

    @extend_schema(summary="上传纪要附件")
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        booking_id = request.data.get("booking")
        title = request.data.get("title") or "会议纪要"
        content = request.data.get("content") or ""
        f = request.FILES.get("file")
        rel, original = "", ""
        if f:
            root = _minute_media_root()
            rel = f"{timezone.now().strftime('%Y%m')}/{os.urandom(8).hex()}_{f.name}"
            full = os.path.join(root, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)
            original = f.name
        minute = MeetingMinute.objects.create(
            booking_id=booking_id, title=title, content=content,
            uploader=request.user, file=rel, original_name=original,
        )
        return ok(MinuteSerializer(minute, context={"request": request}).data)
