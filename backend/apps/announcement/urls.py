"""公告通知域路由。"""
from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet

router = DefaultRouter()
router.register(r"notices", AnnouncementViewSet, basename="announcement")
urlpatterns = router.urls
