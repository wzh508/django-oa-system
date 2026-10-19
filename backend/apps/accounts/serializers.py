"""组织与权限域序列化器。"""
from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from apps.common.masking import mask_value

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


class MaskedField(serializers.CharField):
    """出口自动脱敏的字段。"""

    def __init__(self, *args, mask_kind: str | None = None, **kwargs):
        self.mask_kind = mask_kind
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        from apps.common.masking import should_mask

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user and should_mask(user, self.mask_kind or self.field_name):
            return mask_value(self.mask_kind or self.field_name, value)
        return value


# ------------------------------------------------------------------ 组织
class DeptSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")
    leader_name = serializers.CharField(source="leader.display_name", read_only=True, default="")
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "name", "code", "parent", "parent_name", "leader", "leader_name",
                  "sort", "status", "member_count", "created_at"]
        read_only_fields = ["created_at"]

    def get_member_count(self, obj) -> int:
        return getattr(obj, "member_count", 0) or User.objects.filter(dept_id__in=obj.descendant_ids()).count()


class DeptTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    label = serializers.CharField(source="name", read_only=True)
    value = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "label", "value", "name", "code", "parent", "sort", "status", "children"]

    def get_children(self, obj):
        kids = getattr(obj, "_children_cache", None)
        if kids is None:
            kids = Department.objects.filter(parent=obj, is_deleted=False).order_by("sort", "id")
        return DeptTreeSerializer(kids, many=True, context=self.context).data


class PositionSerializer(serializers.ModelSerializer):
    dept_name = serializers.CharField(source="dept.name", read_only=True, default="")

    class Meta:
        model = Position
        fields = ["id", "name", "code", "dept", "dept_name", "level", "sort"]


# ------------------------------------------------------------------ 用户
class UserListSerializer(serializers.ModelSerializer):
    dept_name = serializers.CharField(source="dept.name", read_only=True, default="")
    position_name = serializers.CharField(source="position.name", read_only=True, default="")
    mobile = MaskedField(mask_kind="mobile", required=False, allow_blank=True)
    id_card = MaskedField(mask_kind="id_card", required=False, allow_blank=True)
    bank_card = MaskedField(mask_kind="bank_card", required=False, allow_blank=True)
    role_names = serializers.SerializerMethodField()
    role_ids = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "employee_no", "dept", "dept_name", "position", "position_name",
                  "mobile", "email", "gender", "status", "hired_at", "id_card", "bank_card", "is_active",
                  "is_superuser", "last_login", "date_joined", "role_names", "role_ids"]

    def get_role_names(self, obj) -> list:
        return [r.name for r in obj.roles.all()]

    def get_role_ids(self, obj) -> list:
        return [r.id for r in obj.roles.all()]


class UserDetailSerializer(UserListSerializer):
    birthday = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + ["birthday", "address", "avatar", "must_change_pwd", "pwd_updated_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, default="Oa@123456")

    class Meta:
        model = User
        fields = ["id", "username", "password", "first_name", "employee_no", "dept", "position",
                  "mobile", "email", "gender", "status", "hired_at", "is_active", "is_superuser"]
        extra_kwargs = {"username": {"required": True}}

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("账号已存在")
        return value

    def create(self, validated_data):
        pwd = validated_data.pop("password", None) or "Oa@123456"
        validated_data["password"] = make_password(pwd)
        return super().create(validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "employee_no", "dept", "position", "mobile", "email", "gender",
                  "status", "hired_at", "birthday", "address", "avatar", "is_active"]
        extra_kwargs = {f: {"required": False} for f in fields} if False else {}


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """个人中心：仅允许本人修改的基础资料字段。"""

    class Meta:
        model = User
        fields = ["first_name", "mobile", "email", "gender", "birthday", "address", "avatar"]
        extra_kwargs = {
            "first_name": {"required": False},
            "mobile": {"required": False},
            "email": {"required": False},
            "gender": {"required": False},
            "birthday": {"required": False},
            "address": {"required": False},
            "avatar": {"required": False},
        }


class AssignRoleSerializer(serializers.Serializer):
    role_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    is_primary = serializers.BooleanField(default=False, required=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=6)


# ------------------------------------------------------------------ 角色权限
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "module", "kind", "description"]


class RoleListSerializer(serializers.ModelSerializer):
    permission_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")

    class Meta:
        model = Role
        fields = ["id", "name", "code", "parent", "parent_name", "description", "data_scope",
                  "data_scope_expr", "status", "sort", "permission_count", "user_count"]

    def get_permission_count(self, obj) -> int:
        return obj.permissions.count()

    def get_user_count(self, obj) -> int:
        return UserRole.objects.filter(role=obj).count()


class RoleDetailSerializer(RoleListSerializer):
    permission_ids = serializers.SerializerMethodField()
    permission_codes = serializers.SerializerMethodField()

    class Meta(RoleListSerializer.Meta):
        fields = RoleListSerializer.Meta.fields + ["permission_ids", "permission_codes"]

    def get_permission_ids(self, obj) -> list:
        return list(obj.permissions.values_list("id", flat=True))

    def get_permission_codes(self, obj) -> list:
        return list(obj.permissions.values_list("code", flat=True))


class RoleWriteSerializer(serializers.ModelSerializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)

    class Meta:
        model = Role
        fields = ["id", "name", "code", "parent", "description", "data_scope", "data_scope_expr",
                  "status", "sort", "permission_ids"]

    def validate_data_scope_expr(self, value):
        if not value:
            return value
        from .services import check_expr

        res = check_expr(value)
        if not res["valid"]:
            raise serializers.ValidationError(f"表达式非法：{res['message']}")
        return value

    def create(self, validated_data):
        perm_ids = validated_data.pop("permission_ids", [])
        role = super().create(validated_data)
        if perm_ids:
            role.permissions.set(Permission.objects.filter(id__in=perm_ids))
        return role

    def update(self, instance, validated_data):
        perm_ids = validated_data.pop("permission_ids", None)
        role = super().update(instance, validated_data)
        if perm_ids is not None:
            role.permissions.set(Permission.objects.filter(id__in=perm_ids))
        return role


class DataScopeRuleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True, default="")

    class Meta:
        model = DataScopeRule
        fields = ["id", "role", "role_name", "resource", "expr", "enabled", "priority"]

    def validate_expr(self, value):
        from .services import check_expr

        res = check_expr(value)
        if not res["valid"]:
            raise serializers.ValidationError(f"表达式非法：{res['message']}")
        return value


class MenuSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")

    class Meta:
        model = Menu
        fields = ["id", "name", "code", "parent", "parent_name", "type", "path", "component",
                  "icon", "sort", "visible", "permission_code", "children"]

    def get_children(self, obj):
        kids = Menu.objects.filter(parent=obj, is_deleted=False).order_by("sort", "id")
        return MenuSerializer(kids, many=True, context=self.context).data


# ------------------------------------------------------------------ 沙盘与解释
class SandboxSimulateSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
    add_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    del_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class SandboxApplySerializer(SandboxSimulateSerializer):
    confirm = serializers.BooleanField(default=False)


class ExplainPermSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    code = serializers.CharField()


class ExplainScopeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    resource = serializers.CharField()
    obj_id = serializers.IntegerField(required=False)


class PermissionChangeLogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="operator.username", read_only=True, default="")

    class Meta:
        model = PermissionChangeLog
        fields = ["id", "batch_id", "change_type", "target_type", "target_id", "before", "after",
                  "impact", "operator", "operator_name", "rolled_back", "created_at"]


# ------------------------------------------------------------------ 日志
class OperationLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)

    class Meta:
        model = OperationLog
        fields = ["id", "created_at", "user", "username", "module", "action", "method", "path",
                  "params", "ip", "status_code", "cost_ms", "sensitive", "prev_hash", "curr_hash"]


class LoginLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginLog
        fields = ["id", "created_at", "username", "ip", "ua", "status", "reason"]


class SensitiveAccessLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True, default="")

    class Meta:
        model = SensitiveAccessLog
        fields = ["id", "created_at", "user", "user_name", "obj_type", "obj_id", "field",
                  "action", "approver", "expire_at", "ip", "remark"]


class SystemParamSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParam
        fields = ["id", "key", "value", "name", "remark"]


# ------------------------------------------------------------------ 认证
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    captcha_key = serializers.CharField(required=False, allow_blank=True, default="")
    captcha_code = serializers.CharField(required=False, allow_blank=True, default="")


class LoginResultSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserListSerializer()
    must_change_pwd = serializers.BooleanField()
