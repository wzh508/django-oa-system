"""站内消息序列化器。"""
from rest_framework import serializers

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.display_name", read_only=True, default="")
    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "recipient", "sender", "sender_name", "title", "content", "level",
                  "level_display", "biz_type", "biz_id", "is_read", "read_at", "created_at"]
        read_only_fields = ["recipient", "sender", "is_read", "read_at"]
