"""会议域序列化器。"""
from rest_framework import serializers
from django.db.models import Q

from .models import MeetingBooking, MeetingMinute, MeetingRoom


class MeetingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingRoom
        fields = ["id", "name", "location", "capacity", "facilities", "equipment", "status",
                  "description", "created_at"]
        read_only_fields = ["created_at"]


class BookingSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source="organizer.first_name", read_only=True, default="")
    room_name = serializers.CharField(source="room.name", read_only=True, default="")
    attendee_ids = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True,
                                         default=list)
    attendee_names = serializers.SerializerMethodField()

    class Meta:
        model = MeetingBooking
        fields = ["id", "room", "room_name", "title", "organizer", "organizer_name",
                  "attendee_ids", "attendee_names", "start", "end", "status", "remark", "created_at"]
        read_only_fields = ["organizer_name", "room_name", "attendee_names", "created_at", "status"]

    def get_attendee_names(self, obj) -> list:
        return [u.first_name or u.username for u in obj.attendees.all()]

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")
        room = attrs.get("room")
        if start and end and end <= start:
            raise serializers.ValidationError("结束时间必须晚于开始时间")
        if room and start and end:
            qs = MeetingBooking.objects.filter(
                room=room,
                status__in=[MeetingBooking.Status.UPCOMING, MeetingBooking.Status.ONGOING],
            ).filter(Q(start__lt=end) & Q(end__gt=start))
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError("该会议室在所选时间段已被预约")
        return attrs

    def create(self, validated_data):
        ids = validated_data.pop("attendee_ids", [])
        booking = super().create(validated_data)
        if ids:
            booking.attendees.set(ids)
        return booking

    def update(self, instance, validated_data):
        ids = validated_data.pop("attendee_ids", None)
        instance = super().update(instance, validated_data)
        if ids is not None:
            instance.attendees.set(ids)
        return instance


class MinuteSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source="uploader.first_name", read_only=True, default="")

    class Meta:
        model = MeetingMinute
        fields = ["id", "booking", "title", "content", "uploader", "uploader_name",
                  "file", "original_name", "created_at"]
        read_only_fields = ["uploader_name", "file", "original_name", "created_at"]
