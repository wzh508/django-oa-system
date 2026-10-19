"""公告通知域接口。"""
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet

from .models import Announcement, AnnouncementRead
from .serializers import AnnouncementSerializer, AnnouncementStatsSerializer


class AnnouncementViewSet(BaseModelViewSet):
    """公告管理：发布、编辑、置顶、阅读统计。"""

    queryset = Announcement.objects.all().select_related("publisher", "dept")
    perm_prefix = "announcement"
    audit_module = "announcement"
    serializer_class = AnnouncementSerializer
    open_actions = {"read"}

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(category=p.get("category"))
        if p.get("level"):
            qs = qs.filter(level=p.get("level"))
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("keyword"):
            qs = qs.filter(title__icontains=p.get("keyword"))
        if p.get("only_published"):
            qs = qs.filter(status=Announcement.Status.PUBLISHED)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            publisher=self.request.user,
            status=Announcement.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    @extend_schema(summary="标记已读", description="员工查看公告时调用，计数 +1")
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        ann = self.get_object()
        AnnouncementRead.objects.get_or_create(announcement=ann, user=request.user)
        Announcement.objects.filter(id=ann.id).update(read_count=F("read_count") + 1)
        return ok(msg="已读")

    @extend_schema(summary="阅读统计", responses=AnnouncementStatsSerializer)
    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Announcement.objects.all()
        # 一次条件聚合取回全部计数类指标，避免多次往返数据库
        agg = qs.aggregate(
            total=Count("id"),
            published=Count("id", filter=Q(status=Announcement.Status.PUBLISHED)),
            draft=Count("id", filter=Q(status=Announcement.Status.DRAFT)),
            top_count=Count("id", filter=Q(is_top=True)),
            total_read=Coalesce(Sum("read_count"), 0),
        )
        month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_count = qs.filter(created_at__gte=month_start).count()
        by_category = list(
            qs.values("category")
            .annotate(count=Count("id"), read_count=Coalesce(Sum("read_count"), 0))
            .order_by("-count")
        )
        top_read = list(
            qs.filter(status=Announcement.Status.PUBLISHED)
            .order_by("-read_count")[:5]
            .values("id", "title", "read_count")
        )
        unread = Announcement.objects.filter(status=Announcement.Status.PUBLISHED).exclude(
            reads__user=request.user
        ).count() if request.user.is_authenticated else 0
        return ok({
            **agg, "month_count": month_count, "by_category": by_category,
            "top_read": top_read, "unread": unread,
        })
