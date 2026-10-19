"""会议域路由。"""
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, MeetingRoomViewSet, MinuteViewSet

router = DefaultRouter()
router.register(r"rooms", MeetingRoomViewSet, basename="meeting-room")
router.register(r"bookings", BookingViewSet, basename="meeting-booking")
router.register(r"minutes", MinuteViewSet, basename="meeting-minute")
urlpatterns = router.urls
