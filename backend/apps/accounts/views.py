"""组织与权限域接口。"""
import base64
import io
import logging
import random
import uuid

from django.contrib.auth import authenticate
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.cache import cache_delete, cache_get, cache_set
from apps.common.exceptions import BusinessException, PermissionDeniedException
from apps.common.hashchain import verify_chain
from apps.common.masking import grant_plaintext, mask_value, revoke_grant
from apps.common.pagination import NoPagination
from apps.common.response import ok
from apps.common.viewsets import BaseModelViewSet, BaseViewSet, client_ip

from .auth_jwt import mark_user_version, register_refresh, revoke_refresh
from .models import (
    DataScopeRule,
    Department,
    LoginLog,
    Menu,
    OperationLog,
    Permission,
    PermissionChangeLog,
    Position,
    Role,
    SensitiveAccessLog,
    SystemParam,
    User,
    UserRole,
)
from .serializers import (
    AssignRoleSerializer,
    ChangePasswordSerializer,
    DataScopeRuleSerializer,
    DeptSerializer,
    DeptTreeSerializer,
    ExplainPermSerializer,
    ExplainScopeSerializer,
    LoginLogSerializer,
    LoginResultSerializer,
    LoginSerializer,
    MenuSerializer,
    OperationLogSerializer,
    PermissionChangeLogSerializer,
    PermissionSerializer,
    PositionSerializer,
    ProfileUpdateSerializer,
    RoleDetailSerializer,
    RoleListSerializer,
    RoleWriteSerializer,
    SandboxApplySerializer,
    SandboxSimulateSerializer,
    SensitiveAccessLogSerializer,
    SystemParamSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from . import services

logger = logging.getLogger(__name__)

CAPTCHA_TTL = 300
LOGIN_FAIL_KEY = "login:fail:{username}"
LOGIN_LOCK_KEY = "login:lock:{username}"


def _lock_remaining(username: str) -> int:
    locked = cache_get(LOGIN_LOCK_KEY.format(username=username))
    return int(locked) if locked else 0


def _gen_captcha_image(code: str) -> bytes:
    """生成验证码图片（纯 PIL，无外部字体依赖）。"""
    from PIL import Image, ImageDraw, ImageFilter

    width, height = 120, 44
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for _ in range(6):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(180, 230),) * 3, width=1)
    for i, ch in enumerate(code):
        draw.text((12 + i * 24, 10), ch, fill=(random.randint(0, 120), random.randint(0, 120), random.randint(0, 160)))
    for _ in range(60):
        draw.point((random.randint(0, width), random.randint(0, height)), fill=(random.randint(0, 255),) * 3)
    image = image.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ 认证
class AuthViewSet(BaseViewSet):
    """登录、验证码、令牌刷新、个人信息。"""

    perm_prefix = "auth"
    open_actions = {"captcha", "login", "refresh", "logout", "profile", "change_password", "menus",
                    "my_permissions", "login_config"}
    serializer_class = LoginSerializer

    def get_permissions(self):
        if self.action in ("captcha", "login", "refresh", "login_config"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(summary="登录页配置", description="告知前端是否需要图形验证码，避免验证码关闭时误拦登录")
    @action(detail=False, methods=["get"], url_path="login-config")
    def login_config(self, request):
        need = SystemParam.objects.filter(key="LOGIN_CAPTCHA_REQUIRED").first()
        required = (need.value != "0") if need else True
        return ok({"captcha_required": required})

    @extend_schema(summary="获取图形验证码", description="返回 base64 PNG 与校验 key，有效期 5 分钟")
    @action(detail=False, methods=["get"])
    def captcha(self, request):
        code = "".join(random.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(4))
        key = uuid.uuid4().hex
        cache_set(f"captcha:{key}", code.lower(), CAPTCHA_TTL)
        img = _gen_captcha_image(code)
        return ok({"key": key, "image": "data:image/png;base64," + base64.b64encode(img).decode(), "ttl": CAPTCHA_TTL})

    @extend_schema(
        summary="登录",
        request=LoginSerializer,
        examples=[OpenApiExample("示例", value={"username": "admin", "password": "Oa@123456",
                                               "captcha_key": "<key>", "captcha_code": "<code>"})],
    )
    @action(detail=False, methods=["post"])
    def login(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        username = data["username"]

        remain = _lock_remaining(username)
        if remain > 0:
            self._log_login(username, None, request, "locked", "账号已锁定")
            raise BusinessException(f"连续登录失败次数过多，请 {remain} 分钟后再试", code=4290, status_code=429)

        from django.conf import settings

        need_captcha = SystemParam.objects.filter(key="LOGIN_CAPTCHA_REQUIRED").first()
        required = (need_captcha.value != "0") if need_captcha else True
        if required:
            key, code = data.get("captcha_key", ""), (data.get("captcha_code") or "").lower()
            real = cache_get(f"captcha:{key}") if key else None
            if not real or real != code:
                raise BusinessException("验证码错误或已过期", code=4001)
            cache_delete(f"captcha:{key}")

        user = authenticate(request, username=username, password=data["password"])
        if user is None or not user.is_active:
            fails = int(cache_get(LOGIN_FAIL_KEY.format(username=username)) or 0) + 1
            cache_set(LOGIN_FAIL_KEY.format(username=username), fails, settings.SECURITY["LOGIN_LOCK_MINUTES"] * 60)
            reason = "账号或密码错误"
            if fails >= settings.SECURITY["LOGIN_FAIL_LIMIT"]:
                cache_set(LOGIN_LOCK_KEY.format(username=username), settings.SECURITY["LOGIN_LOCK_MINUTES"],
                          settings.SECURITY["LOGIN_LOCK_MINUTES"] * 60)
                cache_delete(LOGIN_FAIL_KEY.format(username=username))
                reason = f"连续失败 {fails} 次，账号已锁定 {settings.SECURITY['LOGIN_LOCK_MINUTES']} 分钟"
            self._log_login(username, user, request, "fail", reason)
            raise BusinessException(reason, code=4001)

        cache_delete(LOGIN_FAIL_KEY.format(username=username))
        refresh = RefreshToken.for_user(user)
        register_refresh(refresh, user.id)
        mark_user_version(user.id)
        user.last_login = timezone.now()
        user.last_login_ip = client_ip(request)
        user.save(update_fields=["last_login", "last_login_ip"])
        self._log_login(username, user, request, "success", "")

        return ok({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserListSerializer(user, context={"request": request}).data,
            "must_change_pwd": user.must_change_pwd,
            "expires_in": int(refresh.access_token.lifetime.total_seconds()),
        })

    @action(detail=False, methods=["post"])
    def logout(self, request):
        token = (request.data or {}).get("refresh", "")
        if token:
            revoke_refresh(token)
        return ok(msg="已退出登录")

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def refresh(self, request):
        from rest_framework_simplejwt.exceptions import TokenError

        token = (request.data or {}).get("refresh", "")
        try:
            new_refresh = RefreshToken(token)
            user_id = new_refresh.get("user_id")
            old_jti = new_refresh.get("jti")
            from apps.common.cache import cache_get as _g

            if old_jti and _g(f"jwt:refresh:{old_jti}") is None:
                raise TokenError("refresh 不在白名单")
            user = User.objects.get(id=user_id)
            revoke_refresh(token)
            refresh = RefreshToken.for_user(user)
            register_refresh(refresh, user.id)
            return ok({"access": str(refresh.access_token), "refresh": str(refresh)})
        except Exception:
            raise BusinessException("刷新令牌无效，请重新登录", code=4010, status_code=401)

    @extend_schema(summary="我的菜单树", description="按角色权限动态生成，含按钮级 permission_code")
    @action(detail=False, methods=["get"])
    def menus(self, request):
        return ok(services.get_user_menus(request.user))

    @extend_schema(summary="我的资料", description="GET 读取本人资料；PATCH/PUT 由本人更新基础资料字段")
    @action(detail=False, methods=["get", "patch", "put"])
    def profile(self, request):
        if request.method in ("PATCH", "PUT"):
            ser = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        return ok(UserDetailSerializer(request.user, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def my_permissions(self, request):
        codes = sorted(services.user_permission_codes(request.user))
        if request.user.is_superuser:
            codes = sorted(set(codes) | set(Permission.objects.values_list("code", flat=True)) or ["*"])
        return ok({"codes": codes, "is_superuser": request.user.is_superuser,
                   "roles": [r.code for r in services.effective_roles(request.user)]})

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        ser = ChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(ser.validated_data["old_password"]):
            raise BusinessException("原密码错误", code=4001)
        user.set_password(ser.validated_data["new_password"])
        user.must_change_pwd = False
        user.pwd_updated_at = timezone.now()
        user.save()
        return ok(msg="密码修改成功")

    def _log_login(self, username, user, request, status_, reason=""):
        LoginLog.objects.create(
            username=username,
            user=user if user and user.is_authenticated else None,
            ip=client_ip(request),
            ua=request.META.get("HTTP_USER_AGENT", "")[:200],
            status=status_,
            reason=reason,
        )


# ------------------------------------------------------------------ 用户
class UserViewSet(BaseModelViewSet):
    """用户管理。"""

    queryset = User.objects.all().select_related("dept", "position").prefetch_related("roles")
    perm_prefix = "accounts:user"
    audit_module = "accounts"
    serializer_class = UserListSerializer

    def get_serializer_class(self):
        if self.action in ("retrieve",):
            return UserDetailSerializer
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        dept_id = p.get("dept_id")
        if dept_id:
            qs = qs.filter(dept_id__in=Department.objects.get(id=dept_id).descendant_ids())
        if p.get("status"):
            qs = qs.filter(status=p.get("status"))
        if p.get("keyword"):
            from django.db.models import Q

            kw = p.get("keyword")
            qs = qs.filter(Q(username__icontains=kw) | Q(first_name__icontains=kw) | Q(mobile__icontains=kw) | Q(employee_no__icontains=kw))
        if p.get("role_id"):
            qs = qs.filter(roles__id=p.get("role_id"))
        return qs.distinct()

    @action(detail=True, methods=["post"], url_path="roles")
    def assign_roles(self, request, pk=None):
        """分配角色，写权限变更日志并实时生效。"""
        user = self.get_object()
        ser = AssignRoleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        role_ids = ser.validated_data["role_ids"]
        before = list(user.roles.values_list("id", flat=True))
        UserRole.objects.filter(user=user).delete()
        for rid in role_ids:
            UserRole.objects.get_or_create(user=user, role_id=rid)
        PermissionChangeLog.objects.create(
            batch_id=uuid.uuid4().hex[:16],
            change_type=PermissionChangeLog.ChangeType.GRANT_ROLE,
            target_type="user",
            target_id=user.id,
            before={"role_ids": before},
            after={"role_ids": role_ids},
            operator=request.user if request.user.is_authenticated else None,
        )
        services.invalidate_user_permission_cache()
        return ok({"user_id": user.id, "role_ids": role_ids})

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        user.set_password("Oa@123456")
        user.must_change_pwd = True
        user.pwd_updated_at = timezone.now()
        user.save()
        return ok(msg="已重置为初始密码 Oa@123456，用户下次登录需改密")

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return ok({"is_active": user.is_active})


# ------------------------------------------------------------------ 部门 / 岗位
class DepartmentViewSet(BaseModelViewSet):
    """组织架构树。"""

    queryset = Department.objects.all().select_related("parent", "leader").annotate(member_count=Count("members"))
    perm_prefix = "accounts:dept"
    audit_module = "accounts"
    serializer_class = DeptSerializer

    def get_serializer_class(self):
        return DeptTreeSerializer if self.action == "tree" else DeptSerializer

    @action(detail=False, methods=["get"])
    def tree(self, request):
        roots = Department.objects.filter(parent__isnull=True, is_deleted=False).select_related("parent", "leader").order_by("sort", "id")
        return ok(DeptTreeSerializer(roots, many=True, context={"request": request}).data)

    @extend_schema(summary="部门用户数统计")
    @action(detail=False, methods=["get"])
    def stats(self, request):
        # User 继承 AbstractUser，没有软删除字段（is_deleted），这里按「启用状态」过滤
        rows = (
            User.objects.filter(is_active=True)
            .values("dept__id", "dept__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        return ok(list(rows))


class PositionViewSet(BaseModelViewSet):
    queryset = Position.objects.all().select_related("dept")
    perm_prefix = "accounts:position"
    audit_module = "accounts"
    serializer_class = PositionSerializer


# ------------------------------------------------------------------ 角色 / 权限 / 菜单
class RoleViewSet(BaseModelViewSet):
    queryset = Role.objects.all().select_related("parent").prefetch_related("permissions")
    perm_prefix = "accounts:role"
    audit_module = "accounts"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RoleWriteSerializer
        return RoleDetailSerializer if self.action == "retrieve" else RoleListSerializer

    @action(detail=True, methods=["get"], url_path="effective-permissions")
    def effective_permissions(self, request, pk=None):
        role = self.get_object()
        codes = set()
        for node in role.ancestor_chain():
            codes |= set(node.permissions.values_list("code", flat=True))
        return ok({"role": role.code, "self": list(role.permissions.values_list("code", flat=True)),
                   "inherited": sorted(codes), "chain": [r.code for r in role.ancestor_chain()]})

    @action(detail=False, methods=["get"], url_path="check-cycle")
    def check_cycle(self, request):
        """角色继承防环检测。"""
        cycles = []
        for role in Role.objects.filter(is_deleted=False).select_related("parent"):
            seen, node = {role.id}, role
            for _ in range(64):
                if node.parent_id is None:
                    break
                if node.parent_id in seen:
                    cycles.append({"role": role.code, "loop_at": node.parent.code})
                    break
                seen.add(node.parent_id)
                node = node.parent
        return ok({"cycles": cycles, "healthy": not cycles})


class PermissionViewSet(BaseModelViewSet):
    queryset = Permission.objects.all()
    perm_prefix = "accounts:permission"
    audit_module = "accounts"
    serializer_class = PermissionSerializer

    @action(detail=False, methods=["get"])
    def modules(self, request):
        rows = Permission.objects.values("module").annotate(total=Count("id")).order_by("module")
        return ok(list(rows))


class MenuViewSet(BaseModelViewSet):
    queryset = Menu.objects.all().select_related("parent")
    perm_prefix = "accounts:menu"
    audit_module = "accounts"
    serializer_class = MenuSerializer

    @action(detail=False, methods=["get"], pagination_class=NoPagination)
    def tree(self, request):
        roots = Menu.objects.filter(parent__isnull=True, is_deleted=False).order_by("sort", "id")
        return ok(MenuSerializer(roots, many=True, context={"request": request}).data)


class DataScopeRuleViewSet(BaseModelViewSet):
    queryset = DataScopeRule.objects.all().select_related("role")
    perm_prefix = "accounts:scope"
    audit_module = "accounts"
    serializer_class = DataScopeRuleSerializer

    @action(detail=False, methods=["post"])
    def validate(self, request):
        expr = (request.data or {}).get("expr", "")
        return ok(services.check_expr(expr))


# ------------------------------------------------------------------ 权限沙盘
class PermissionSandboxViewSet(BaseViewSet):
    """权限沙盘：变更影响面预演、落库、回滚。"""

    perm_prefix = "accounts:sandbox"
    audit_module = "accounts"
    queryset = PermissionChangeLog.objects.none()
    serializer_class = SandboxSimulateSerializer

    @extend_schema(summary="权限变更影响面预演", request=SandboxSimulateSerializer)
    @action(detail=False, methods=["post"], url_path="simulate")
    def simulate(self, request):
        ser = SandboxSimulateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        return ok(services.simulate_role_permission_change(d["role_id"], d.get("add_codes", []), d.get("del_codes", [])))

    @extend_schema(summary="确认落库生效")
    @action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        ser = SandboxApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get("confirm"):
            raise BusinessException("请先确认影响面后再生效", code=4002)
        d = ser.validated_data
        result = services.apply_role_permission_change(d["role_id"], d.get("add_codes", []), d.get("del_codes", []), request.user)
        if "error" in result:
            raise BusinessException(result["error"], code=4004)
        return ok(result)

    @extend_schema(summary="按批次回滚权限变更")
    @action(detail=False, methods=["post"], url_path="rollback")
    def rollback(self, request):
        batch_id = (request.data or {}).get("batch_id", "")
        result = services.rollback_permission_change(batch_id, request.user)
        if "error" in result:
            raise BusinessException(result["error"], code=4004)
        return ok(result)

    @action(detail=False, methods=["get"], url_path="changes")
    def changes(self, request):
        qs = PermissionChangeLog.objects.all().order_by("-id")[:100]
        return ok(PermissionChangeLogSerializer(qs, many=True).data)


class ExplainViewSet(BaseViewSet):
    """权限与数据范围决策可解释。"""

    perm_prefix = "accounts:explain"
    audit_module = "accounts"
    queryset = PermissionChangeLog.objects.none()
    serializer_class = ExplainPermSerializer
    open_actions = {"permission", "data_scope"}

    @extend_schema(summary="权限决策解释", parameters=[ExplainPermSerializer])
    @action(detail=False, methods=["get", "post"], url_path="permission")
    def permission(self, request):
        src = request.query_params if request.method == "GET" else request.data
        code = src.get("code", "")
        user_id = src.get("user_id")
        user = request.user
        if user_id:
            user = User.objects.filter(id=user_id).first() or user
        if not code:
            raise BusinessException("缺少 code 参数", code=4001)
        return ok(services.explain_permission(user, code))

    @extend_schema(summary="数据范围决策解释", parameters=[ExplainScopeSerializer])
    @action(detail=False, methods=["get", "post"], url_path="data-scope")
    def data_scope(self, request):
        src = request.query_params if request.method == "GET" else request.data
        resource = src.get("resource", "")
        user_id = src.get("user_id")
        obj_id = src.get("obj_id")
        user = request.user
        if user_id:
            user = User.objects.filter(id=user_id).first() or user
        if not resource:
            raise BusinessException("缺少 resource 参数", code=4001)
        return ok(services.explain_data_scope(user, resource, obj_id))


# ------------------------------------------------------------------ 日志
class OperationLogViewSet(BaseViewSet):
    """操作日志（哈希链防篡改）。"""

    queryset = OperationLog.objects.all().select_related("user")
    perm_prefix = "accounts:oplog"
    audit_module = "accounts"
    serializer_class = OperationLogSerializer

    @extend_schema(summary="操作日志列表")
    def list(self, request, *args, **kwargs):
        return self._paginated(request)

    @action(detail=False, methods=["get"], url_path="list")
    def list_logs(self, request):
        return self._paginated(request)

    def _paginated(self, request):
        qs = self.queryset
        if request.query_params.get("user_id"):
            qs = qs.filter(user_id=request.query_params.get("user_id"))
        if request.query_params.get("module"):
            qs = qs.filter(module=request.query_params.get("module"))
        if request.query_params.get("action"):
            qs = qs.filter(action=request.query_params.get("action"))
        if request.query_params.get("sensitive") == "1":
            qs = qs.filter(sensitive=True)
        if request.query_params.get("date_from"):
            qs = qs.filter(created_at__date__gte=request.query_params.get("date_from"))
        if request.query_params.get("date_to"):
            qs = qs.filter(created_at__date__lte=request.query_params.get("date_to"))
        qs = qs.order_by("-id")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(OperationLogSerializer(page, many=True).data) if page is not None else ok(
            OperationLogSerializer(qs[:100], many=True).data)

    @extend_schema(summary="哈希链完整性校验", description="任何一条被篡改都会被定位")
    @action(detail=False, methods=["post", "get"], url_path="verify")
    def verify(self, request):
        rows = list(OperationLog.objects.order_by("id").values("id", "prev_hash", "curr_hash", "content"))
        result = verify_chain(rows)
        result["checked_at"] = timezone.now().isoformat()
        return ok(result)


class LoginLogViewSet(BaseViewSet):
    queryset = LoginLog.objects.all()
    perm_prefix = "accounts:loginlog"
    audit_module = "accounts"
    serializer_class = LoginLogSerializer

    def list(self, request, *args, **kwargs):
        return self._page(request)

    @action(detail=False, methods=["get"], url_path="list")
    def list_logs(self, request):
        return self._page(request)

    def _page(self, request):
        qs = self.queryset.order_by("-id")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params.get("status"))
        if request.query_params.get("username"):
            qs = qs.filter(username__icontains=request.query_params.get("username"))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(LoginLogSerializer(page, many=True).data) if page is not None else ok(
            LoginLogSerializer(qs[:100], many=True).data)


class SensitiveAccessViewSet(BaseViewSet):
    """敏感字段二次授权与明文查看（全程留痕）。"""

    queryset = SensitiveAccessLog.objects.all().select_related("user", "approver")
    perm_prefix = "accounts:sensitive"
    audit_module = "accounts"
    serializer_class = SensitiveAccessLogSerializer
    open_actions = {"apply", "view"}

    @extend_schema(summary="申请查看明文")
    @action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        d = request.data or {}
        obj_type, obj_id, field = d.get("obj_type"), d.get("obj_id"), d.get("field")
        if not all([obj_type, obj_id, field]):
            raise BusinessException("缺少 obj_type / obj_id / field", code=4001)
        log = SensitiveAccessLog.objects.create(
            user=request.user, obj_type=obj_type, obj_id=str(obj_id), field=field,
            action="apply", ip=client_ip(request), remark=d.get("reason", ""),
        )
        return ok({"apply_id": log.id, "status": "pending", "msg": "已提交申请，等待审批"})

    @extend_schema(summary="审批授权查看明文（限管理员/HR）")
    @action(detail=False, methods=["post"], url_path="grant")
    def grant(self, request):
        d = request.data or {}
        apply_id = d.get("apply_id")
        log = SensitiveAccessLog.objects.filter(id=apply_id, action="apply").first()
        if not log:
            raise BusinessException("申请不存在", code=4040, status_code=404)
        if not (request.user.is_superuser or services.user_has_perm(request.user, "sensitive:grant")):
            raise PermissionDeniedException("无审批授权权限")
        minutes = int(d.get("minutes") or 30)
        grant_plaintext(log.user_id, log.field, log.obj_type, log.obj_id, minutes)
        SensitiveAccessLog.objects.create(
            user=log.user, obj_type=log.obj_type, obj_id=log.obj_id, field=log.field,
            action="grant", approver=request.user, expire_at=timezone.now() + timezone.timedelta(minutes=minutes),
            ip=client_ip(request),
        )
        return ok({"granted": True, "minutes": minutes, "user_id": log.user_id, "field": log.field})

    @extend_schema(summary="查看明文（需有效授权）")
    @action(detail=False, methods=["get"], url_path="view")
    def view(self, request):
        obj_type = request.query_params.get("obj_type")
        obj_id = request.query_params.get("obj_id")
        field = request.query_params.get("field")
        model_map = {"user": User}
        model = model_map.get(obj_type)
        if model is None:
            raise BusinessException("暂不支持该对象类型", code=4001)
        obj = model.objects.filter(id=obj_id).first()
        if obj is None:
            raise BusinessException("对象不存在", code=4040, status_code=404)
        from apps.common.masking import has_grant
        from apps.common.masking import should_mask as _should_mask

        if _should_mask(request.user, field) and not has_grant(request.user.id, field, obj_type, obj_id):
            SensitiveAccessLog.objects.create(user=request.user, obj_type=obj_type, obj_id=str(obj_id),
                                              field=field, action="deny", ip=client_ip(request))
            raise PermissionDeniedException("未获得明文查看授权，请先申请")
        raw = getattr(obj, field, "")
        SensitiveAccessLog.objects.create(user=request.user, obj_type=obj_type, obj_id=str(obj_id),
                                          field=field, action="view", ip=client_ip(request))
        revoke_grant(request.user.id, field, obj_type, obj_id)
        return ok({"field": field, "value": raw})

    @action(detail=False, methods=["get"], url_path="logs")
    def logs(self, request):
        qs = self.queryset.order_by("-id")[:100]
        return ok(SensitiveAccessLogSerializer(qs, many=True).data)


class SystemParamViewSet(BaseModelViewSet):
    queryset = SystemParam.objects.all()
    perm_prefix = "accounts:param"
    audit_module = "accounts"
    serializer_class = SystemParamSerializer
