"""文档中心域序列化器。"""
from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.first_name", read_only=True, default="")
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")
    child_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "name", "parent", "parent_name", "is_folder", "category", "owner",
                  "owner_name", "dept", "file", "original_name", "mime", "size", "version",
                  "share_type", "tags", "description", "download_count", "child_count", "created_at"]
        read_only_fields = ["file", "original_name", "mime", "size", "version",
                            "download_count", "created_at", "owner_name", "parent_name", "child_count"]

    def get_child_count(self, obj) -> int:
        if obj.is_folder:
            return Document.objects.filter(parent=obj).count()
        return 0
