"""公告通知域序列化器。"""
from rest_framework import serializers

from .models import Announcement, AnnouncementRead


class AnnouncementSerializer(serializers.ModelSerializer):
    publisher_name = serializers.CharField(source="publisher.first_name", read_only=True, default="")
    dept_name = serializers.CharField(source="dept.name", read_only=True, default="")
    read_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["id", "title", "content", "category", "level", "status", "publisher",
                  "publisher_name", "dept", "dept_name", "is_top", "published_at",
                  "expire_at", "read_count", "read_by_me", "created_at"]
        read_only_fields = ["read_count", "published_at", "created_at", "read_by_me"]

    def get_read_by_me(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        return AnnouncementRead.objects.filter(announcement=obj, user=request.user).exists()


class AnnouncementStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    published = serializers.IntegerField()
    draft = serializers.IntegerField()
    top_count = serializers.IntegerField()
    total_read = serializers.IntegerField()
    month_count = serializers.IntegerField()
    by_category = serializers.ListField()
    top_read = serializers.ListField()
    unread = serializers.IntegerField()
