from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/workflow/", include("apps.workflow.urls")),
    path("api/v1/attendance/", include("apps.attendance.urls")),
    # 以下模块在对应 app 落地后逐个启用（避免半成品路由导致整体不可用）
    path("api/v1/announcement/", include("apps.announcement.urls")),
    path("api/v1/document/", include("apps.document.urls")),
    path("api/v1/hr/", include("apps.hr.urls")),
    # 报销模块（ExpenseRequest）已并入 workflow app，路由为 /api/v1/workflow/requests/
    path("api/v1/message/", include("apps.message.urls")),
    path("api/v1/meeting/", include("apps.meeting.urls")),
    path("api/v1/schedule/", include("apps.schedule.urls")),
    path("api/v1/insight/", include("apps.insight.urls")),
    path("api/v1/lowcode/", include("apps.lowcode.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
