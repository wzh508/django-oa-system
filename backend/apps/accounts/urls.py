from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthViewSet,
    DataScopeRuleViewSet,
    DepartmentViewSet,
    ExplainViewSet,
    LoginLogViewSet,
    MenuViewSet,
    OperationLogViewSet,
    PermissionSandboxViewSet,
    PermissionViewSet,
    PositionViewSet,
    RoleViewSet,
    SensitiveAccessViewSet,
    SystemParamViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
router.register("users", UserViewSet, basename="user")
router.register("departments", DepartmentViewSet, basename="department")
router.register("positions", PositionViewSet, basename="position")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("menus", MenuViewSet, basename="menu")
router.register("data-scope-rules", DataScopeRuleViewSet, basename="data-scope-rule")
router.register("permission-sandbox", PermissionSandboxViewSet, basename="permission-sandbox")
router.register("explain", ExplainViewSet, basename="explain")
router.register("operation-logs", OperationLogViewSet, basename="operation-log")
router.register("login-logs", LoginLogViewSet, basename="login-log")
router.register("sensitive", SensitiveAccessViewSet, basename="sensitive")
router.register("system-params", SystemParamViewSet, basename="system-param")

urlpatterns = [path("", include(router.urls))]
