"""日程与任务域路由。"""
from rest_framework.routers import DefaultRouter

from .views import ScheduleViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"schedules", ScheduleViewSet, basename="schedule")
router.register(r"tasks", TaskViewSet, basename="task")
urlpatterns = router.urls
