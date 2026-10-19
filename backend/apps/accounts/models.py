"""组织与权限域模型。"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel, TimeStampedModel


class Department(BaseModel):
    """部门（自关联树，支持无限层级）。"""

    name = models.CharField("部门名称", max_length=64)
    code = models.CharField("部门编码", max_length=64, unique=True)
    parent = models.ForeignKey(
        "self", verbose_name="上级部门", null=True, blank=True,
        on_delete=models.CASCADE, related_name="children", db_index=True,
    )
    leader = models.ForeignKey(
        "accounts.User", verbose_name="部门负责人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="led_departments",
    )
    sort = models.IntegerField("排序", default=0)
    status = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "部门"
        verbose_name_plural = "部门"
        ordering = ["sort", "id"]
        indexes = [models.Index(fields=["parent", "status"])]

    def __str__(self):
        return self.name

    @property
    def full_path(self) -> str:
        names, node = [], self
        depth = 0
        while node is not None and depth < 32:
            names.append(node.name)
            node = node.parent
            depth += 1
        return "/".join(reversed(names))

    def descendant_ids(self, include_self: bool = True) -> list:
        """返回本部门及全部下级部门 id（BFS，最多 20 层防环）。"""
        result = [] if not include_self else [self.id]
        level = [self.id]
        for _ in range(20):
            children = list(
                Department.objects.filter(parent_id__in=level, is_deleted=False).values_list("id", flat=True)
            )
            if not children:
                break
            result.extend(children)
            level = children
        return result


class Position(BaseModel):
    """岗位。"""

    name = models.CharField("岗位名称", max_length=64)
    code = models.CharField("岗位编码", max_length=64, unique=True)
    dept = models.ForeignKey(Department, verbose_name="所属部门", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="positions", db_index=True)
    level = models.CharField("职级", max_length=32, blank=True, default="")
    sort = models.IntegerField("排序", default=0)

    class Meta:
        verbose_name = "岗位"
        verbose_name_plural = "岗位"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """扩展用户。"""

    class Gender(models.IntegerChoices):
        UNKNOWN = 0, "未知"
        MALE = 1, "男"
        FEMALE = 2, "女"

    class Status(models.TextChoices):
        ACTIVE = "active", "在职"
        PROBATION = "probation", "试用期"
        LEAVE = "leave", "休假"
        RESIGNED = "resigned", "离职"
        DISABLED = "disabled", "禁用"

    employee_no = models.CharField("工号", max_length=32, unique=True, null=True, blank=True, db_index=True)
    dept = models.ForeignKey(Department, verbose_name="所属部门", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="members", db_index=True)
    position = models.ForeignKey(Position, verbose_name="岗位", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="holders")
    mobile = models.CharField("手机号", max_length=20, blank=True, default="")
    email = models.EmailField("邮箱", blank=True, default="")
    avatar = models.CharField("头像", max_length=255, blank=True, default="")
    gender = models.IntegerField("性别", choices=Gender.choices, default=Gender.UNKNOWN)
    status = models.CharField("在职状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    hired_at = models.DateField("入职日期", null=True, blank=True)
    birthday = models.DateField("生日", null=True, blank=True)
    id_card = models.CharField("身份证号", max_length=32, blank=True, default="")
    bank_card = models.CharField("银行卡号", max_length=32, blank=True, default="")
    address = models.CharField("住址", max_length=255, blank=True, default="")
    last_login_ip = models.CharField("最近登录IP", max_length=64, blank=True, default="")
    pwd_updated_at = models.DateTimeField("密码修改时间", null=True, blank=True)
    must_change_pwd = models.BooleanField("强制改密", default=False)
    roles = models.ManyToManyField("accounts.Role", through="UserRole", related_name="users", blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = "用户"
        verbose_name_plural = "用户"
        swappable = "AUTH_USER_MODEL"
        indexes = [
            models.Index(fields=["dept", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.username}({self.get_full_name() or self.username})"

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.first_name or self.username


class Role(BaseModel):
    """角色，支持 parent 自关联实现角色继承。"""

    class DataScope(models.TextChoices):
        SELF = "SELF", "仅本人"
        DEPT = "DEPT", "本部门"
        DEPT_TREE = "DEPT_TREE", "本部门及下级"
        ALL = "ALL", "全部"
        CUSTOM = "CUSTOM", "自定义表达式"

    name = models.CharField("角色名称", max_length=64)
    code = models.CharField("角色编码", max_length=64, unique=True)
    parent = models.ForeignKey("self", verbose_name="父角色", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="children")
    description = models.CharField("描述", max_length=255, blank=True, default="")
    data_scope = models.CharField("数据范围", max_length=16, choices=DataScope.choices, default=DataScope.SELF)
    data_scope_expr = models.TextField(
        "数据范围表达式",
        blank=True,
        default="",
        help_text="如：SELF | DEPT ；或 status=OWN_DEPT and amount < 5000",
    )
    status = models.BooleanField("启用", default=True)
    sort = models.IntegerField("排序", default=0)
    permissions = models.ManyToManyField("accounts.Permission", through="RolePermission",
                                         related_name="roles", blank=True)

    class Meta:
        verbose_name = "角色"
        verbose_name_plural = "角色"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.name

    def ancestor_chain(self) -> list:
        """自下而上返回 [self, parent, grandparent...]，带防环。"""
        chain, node, seen = [], self, {self.id}
        for _ in range(32):
            chain.append(node)
            if node.parent_id is None or node.parent_id in seen:
                break
            seen.add(node.parent_id)
            node = node.parent
        return chain


class Permission(BaseModel):
    """权限点，code 全局唯一，形如 attendance:record:export。"""

    class Kind(models.TextChoices):
        API = "api", "接口"
        MENU = "menu", "菜单"
        BUTTON = "button", "按钮"

    code = models.CharField("权限码", max_length=128, unique=True, db_index=True)
    name = models.CharField("权限名称", max_length=64)
    module = models.CharField("所属模块", max_length=64, blank=True, default="", db_index=True)
    kind = models.CharField("类型", max_length=16, choices=Kind.choices, default=Kind.API)
    description = models.CharField("描述", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "权限点"
        verbose_name_plural = "权限点"
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.code}"


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "permission")
        verbose_name = "角色权限"


class UserRole(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    is_primary = models.BooleanField("主角色", default=False)

    class Meta:
        unique_together = ("user", "role")
        verbose_name = "用户角色"


class Menu(BaseModel):
    """菜单树，type 区分 目录 / 菜单 / 按钮，实现按钮级权限。"""

    class Type(models.TextChoices):
        DIR = "dir", "目录"
        MENU = "menu", "菜单"
        BUTTON = "button", "按钮"

    parent = models.ForeignKey("self", verbose_name="上级菜单", null=True, blank=True,
                               on_delete=models.CASCADE, related_name="children", db_index=True)
    name = models.CharField("菜单名称", max_length=64)
    code = models.CharField("菜单编码", max_length=128, unique=True)
    type = models.CharField("类型", max_length=16, choices=Type.choices, default=Type.MENU)
    path = models.CharField("路由地址", max_length=255, blank=True, default="")
    component = models.CharField("前端组件", max_length=255, blank=True, default="")
    icon = models.CharField("图标", max_length=64, blank=True, default="")
    sort = models.IntegerField("排序", default=0)
    visible = models.BooleanField("是否显示", default=True)
    permission_code = models.CharField("权限码", max_length=128, blank=True, default="", db_index=True,
                                       help_text="按钮级权限码，前端 v-permission 据此控制显隐")

    class Meta:
        verbose_name = "菜单"
        verbose_name_plural = "菜单"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.name


class DataScopeRule(BaseModel):
    """数据范围规则（创新点）：按资源声明自定义表达式。"""

    role = models.ForeignKey(Role, verbose_name="角色", on_delete=models.CASCADE, related_name="scope_rules")
    resource = models.CharField("资源标识", max_length=128, db_index=True,
                                help_text="形如 attendance.record / workflow.instance")
    expr = models.TextField("表达式", help_text="如 SELF | DEPT ；或 status=OWN_DEPT and amount < 5000")
    enabled = models.BooleanField("启用", default=True)
    priority = models.IntegerField("优先级", default=0)

    class Meta:
        verbose_name = "数据范围规则"
        verbose_name_plural = "数据范围规则"
        unique_together = ("role", "resource")
        ordering = ["-priority", "id"]


class PermissionChangeLog(TimeStampedModel):
    """权限变更记录（权限沙盘与影响面分析用）。"""

    class ChangeType(models.TextChoices):
        GRANT_ROLE = "grant_role", "分配角色"
        REVOKE_ROLE = "revoke_role", "回收角色"
        ROLE_PERM_ADD = "role_perm_add", "角色增权限"
        ROLE_PERM_DEL = "role_perm_del", "角色减权限"
        SCOPE_CHANGE = "scope_change", "数据范围变更"
        ROLLBACK = "rollback", "回滚"

    batch_id = models.CharField("批次号", max_length=64, db_index=True)
    change_type = models.CharField("变更类型", max_length=32, choices=ChangeType.choices)
    target_type = models.CharField("对象类型", max_length=32, help_text="user / role")
    target_id = models.BigIntegerField("对象ID", db_index=True)
    before = models.JSONField("变更前", null=True, blank=True)
    after = models.JSONField("变更后", null=True, blank=True)
    impact = models.JSONField("影响面报告", null=True, blank=True)
    operator = models.ForeignKey(User, verbose_name="操作人", null=True, on_delete=models.SET_NULL)
    rolled_back = models.BooleanField("已回滚", default=False)

    class Meta:
        verbose_name = "权限变更记录"
        verbose_name_plural = "权限变更记录"
        ordering = ["-id"]


class OperationLog(models.Model):
    """操作日志（哈希链防篡改）。不使用软删除，保证链完整。"""

    created_at = models.DateTimeField("时间", default=timezone.now, db_index=True)
    user = models.ForeignKey(User, verbose_name="操作人", null=True, blank=True, on_delete=models.SET_NULL,
                             db_index=True, related_name="operation_logs")
    username = models.CharField("账号", max_length=150, blank=True, default="")
    module = models.CharField("模块", max_length=64, blank=True, default="", db_index=True)
    action = models.CharField("动作", max_length=64, blank=True, default="")
    method = models.CharField("HTTP方法", max_length=10, blank=True, default="")
    path = models.CharField("请求路径", max_length=255, blank=True, default="")
    params = models.JSONField("请求参数", null=True, blank=True)
    ip = models.CharField("IP", max_length=64, blank=True, default="")
    ua = models.CharField("UA", max_length=255, blank=True, default="")
    status_code = models.IntegerField("响应码", default=200)
    cost_ms = models.IntegerField("耗时ms", default=0)
    sensitive = models.BooleanField("敏感操作", default=False)
    prev_hash = models.CharField("前序哈希", max_length=64, db_index=True)
    curr_hash = models.CharField("当前哈希", max_length=64, unique=True)
    content = models.TextField("规范化内容")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["id"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"#{self.id} {self.action}"


class LoginLog(models.Model):
    created_at = models.DateTimeField("时间", default=timezone.now, db_index=True)
    username = models.CharField("账号", max_length=150, blank=True, default="", db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_logs")
    ip = models.CharField("IP", max_length=64, blank=True, default="")
    ua = models.CharField("UA", max_length=255, blank=True, default="")
    status = models.CharField("结果", max_length=16, default="success",
                              choices=[("success", "成功"), ("fail", "失败"), ("locked", "锁定")])
    reason = models.CharField("原因", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "登录日志"
        verbose_name_plural = "登录日志"
        ordering = ["-id"]


class SensitiveAccessLog(models.Model):
    """敏感字段二次授权与明文查看留痕。"""

    created_at = models.DateTimeField("时间", default=timezone.now, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sensitive_logs")
    obj_type = models.CharField("对象类型", max_length=64, db_index=True)
    obj_id = models.CharField("对象ID", max_length=64)
    field = models.CharField("字段", max_length=64)
    action = models.CharField("动作", max_length=16,
                              choices=[("apply", "申请"), ("grant", "授权"), ("view", "查看明文"), ("deny", "拒绝")])
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_grants")
    expire_at = models.DateTimeField("过期时间", null=True, blank=True)
    ip = models.CharField("IP", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "敏感字段访问日志"
        verbose_name_plural = "敏感字段访问日志"
        ordering = ["-id"]


class SystemParam(BaseModel):
    """系统参数。"""

    key = models.CharField("参数键", max_length=64, unique=True)
    value = models.TextField("参数值", blank=True, default="")
    name = models.CharField("参数名称", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "系统参数"
        verbose_name_plural = "系统参数"
