"""权限核心服务。

所有权限计算必须走本模块，禁止在 view / serializer 里自行查询权限表。
缓存 key 带权限版本号，权限变更后 bump 版本即可全站实时生效（无需重新登录）。
"""
import logging
from typing import Iterable

from django.apps import apps as django_apps
from django.db.models import Q
from django.utils import timezone

from apps.common.cache import (
    bump_perm_version,
    cache_delete_pattern,
    cached,
    get_perm_version,
    perm_cache_key,
)

from .expr import ExprError, parse_expr, resolve_node, validate_expr
from .models import (
    DataScopeRule,
    Menu,
    Permission,
    PermissionChangeLog,
    Role,
    UserRole,
)

logger = logging.getLogger(__name__)

CACHE_TTL = 300


# ------------------------------------------------------------------ 角色
def user_roles(user):
    """用户直接持有的启用角色。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return list(
        Role.objects.filter(userrole__user=user, status=True, is_deleted=False)
        .select_related("parent")
        .order_by("id")
    )


def role_ancestors_with_self(role: Role) -> list:
    """角色继承链（含自身），带防环。"""
    return role.ancestor_chain()


def effective_roles(user) -> list:
    """递归取所有角色及其祖先角色（并集），防环。"""
    seen, out = set(), []
    for role in user_roles(user):
        for node in role.ancestor_chain():
            if node.id in seen:
                continue
            seen.add(node.id)
            out.append(node)
    return out


# ------------------------------------------------------------------ 权限码
def _perm_codes_uncached(user) -> set:
    roles = effective_roles(user)
    if not roles:
        return set()
    role_ids = [r.id for r in roles]
    return set(
        Permission.objects.filter(rolepermission__role_id__in=role_ids, is_deleted=False).values_list("code", flat=True)
    )


def user_permission_codes(user) -> set:
    """用户有效权限码集合（含角色继承）。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    key = perm_cache_key(user.id, "codes")
    from apps.common.cache import cache_get, cache_set

    hit = cache_get(key)
    if hit is not None:
        return set(hit)
    codes = _perm_codes_uncached(user)
    cache_set(key, list(codes), CACHE_TTL)
    return codes


def user_has_perm(user, code: str) -> bool:
    """核心服务函数：判断用户是否拥有某权限码。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not code:
        return False
    codes = user_permission_codes(user)
    if code in codes:
        return True
    # 支持模块级通配：attendance:* 命中 attendance:record:export
    module = code.split(":", 1)[0] if ":" in code else code
    return f"{module}:*" in codes


def require_perm(user, code: str) -> None:
    from apps.common.exceptions import PermissionDeniedException

    if not user_has_perm(user, code):
        raise PermissionDeniedException(f"缺少权限：{code}")


# ------------------------------------------------------------------ 菜单
def get_user_menus(user) -> list:
    """按权限生成菜单树（含按钮级 permission_code）。"""
    if user is None:
        return []
    if getattr(user, "is_superuser", False):
        menus = list(Menu.objects.filter(is_deleted=True))  # 占位，下面覆盖
        menus = list(Menu.objects.filter(is_deleted=False).order_by("sort", "id"))
    else:
        codes = user_permission_codes(user)
        q = Q(permission_code="") | Q(permission_code__in=codes) | Q(type=Menu.Type.DIR)
        menus = list(Menu.objects.filter(is_deleted=False).filter(q).order_by("sort", "id"))

    tree, index = [], {}
    for m in menus:
        index[m.id] = {
            "id": m.id,
            "name": m.name,
            "code": m.code,
            "type": m.type,
            "path": m.path,
            "component": m.component,
            "icon": m.icon,
            "sort": m.sort,
            "visible": m.visible,
            "permission_code": m.permission_code,
            "children": [],
        }
    for m in menus:
        node = index[m.id]
        if m.parent_id and m.parent_id in index:
            index[m.parent_id]["children"].append(node)
        else:
            tree.append(node)
    return tree


def get_user_menu_codes(user) -> set:
    return {m["code"] for m in get_user_menus(user)}


# ------------------------------------------------------------------ 数据范围
def get_data_scope(user, resource: str):
    """返回该用户在该资源上的数据范围定义（取优先级最高的启用规则）。"""
    if user is None or getattr(user, "is_superuser", False):
        return None
    roles = effective_roles(user)
    if not roles:
        return None
    rule = (
        DataScopeRule.objects.filter(role__in=roles, resource=resource, enabled=True, is_deleted=False)
        .select_related("role")
        .order_by("-priority", "id")
        .first()
    )
    if rule is not None:
        return {"source": "rule", "role": rule.role.code, "expr": rule.expr, "rule_id": rule.id}
    # 回退到角色上的默认数据范围
    for role in sorted(roles, key=lambda r: _scope_rank(r), reverse=True):
        if role.data_scope == Role.DataScope.CUSTOM and role.data_scope_expr:
            return {"source": "role", "role": role.code, "expr": role.data_scope_expr, "rule_id": None}
        return {"source": "role", "role": role.code, "expr": role.data_scope, "rule_id": None}
    return None


def _scope_rank(role: Role) -> int:
    order = {
        Role.DataScope.ALL: 4,
        Role.DataScope.DEPT_TREE: 3,
        Role.DataScope.DEPT: 2,
        Role.DataScope.CUSTOM: 1,
        Role.DataScope.SELF: 0,
    }
    return order.get(role.data_scope, 0)


def resolve_data_scope_expr(expr: str, user, user_field: str = "created_by") -> Q:
    """表达式 → ORM Q 对象。"""
    if not expr:
        return Q(pk__in=[])
    node = parse_expr(expr)
    return resolve_node(node, user, user_field=user_field)


def get_data_scope_q(user, resource: str, user_field: str = "created_by"):
    """数据范围过滤条件。返回 None 表示不做限制（如超管）。"""
    if user is None or getattr(user, "is_superuser", False):
        return None
    scope = get_data_scope(user, resource)
    if scope is None:
        # 无配置时保守：仅本人
        return Q(**{user_field: user})
    try:
        return resolve_data_scope_expr(scope["expr"], user, user_field=user_field)
    except ExprError as exc:
        logger.warning("data scope expr error: %s (%s)", scope["expr"], exc)
        return Q(pk__in=[])


def explain_data_scope(user, model_label: str, obj_id=None) -> dict:
    """数据范围决策可解释：返回结构化决策链。"""
    chain: list = []
    if getattr(user, "is_superuser", False):
        chain.append({"step": "超级管理员旁路", "detail": "is_superuser=True", "result": "allow"})
        return {"allowed": True, "resource": model_label, "chain": chain, "expression": "ALL"}

    scope = get_data_scope(user, model_label)
    if scope is None:
        chain.append({"step": "未配置数据范围", "detail": "回退为仅本人", "result": "restrict"})
        expr = "SELF"
    else:
        chain.append({
            "step": "命中数据范围规则",
            "detail": f"来源={scope['source']} 角色={scope['role']} 规则ID={scope['rule_id']}",
            "result": "restrict",
        })
        expr = scope["expr"]

    chain.append({"step": "解析表达式", "detail": expr, "result": "ok"})
    q = get_data_scope_q(user, model_label)
    chain.append({"step": "生成 ORM 条件", "detail": str(q), "result": "ok"})

    allowed = None
    if obj_id is not None:
        try:
            app_label, model_name = model_label.split(".")
            model = django_apps.get_model(app_label, model_name)
            allowed = model.objects.filter(q).filter(pk=obj_id).exists()
            chain.append({"step": "对象可见性判定", "detail": f"obj_id={obj_id}", "result": "allow" if allowed else "deny"})
        except Exception as exc:
            chain.append({"step": "对象可见性判定", "detail": str(exc), "result": "error"})
    return {"allowed": allowed, "resource": model_label, "expression": expr, "chain": chain}


def explain_permission(user, code: str) -> dict:
    """权限决策可解释：返回命中了哪个角色、哪条权限点。"""
    chain: list = []
    if getattr(user, "is_superuser", False):
        chain.append({"step": "超级管理员旁路", "detail": "is_superuser=True", "result": "allow"})
        return {"allowed": True, "code": code, "chain": chain}

    roles = effective_roles(user)
    if not roles:
        chain.append({"step": "获取有效角色", "detail": "用户无任何角色", "result": "deny"})
        return {"allowed": False, "code": code, "chain": chain}

    chain.append({"step": "展开有效角色（含继承）", "detail": ", ".join(r.code for r in roles), "result": "ok"})
    role_ids = [r.id for r in roles]
    perm = Permission.objects.filter(rolepermission__role_id__in=role_ids, code=code, is_deleted=False).first()
    if perm is not None:
        owner = Role.objects.filter(permissions=perm, id__in=role_ids).first()
        chain.append({"step": "命中权限点", "detail": f"{perm.code}（{perm.name}）", "result": "ok"})
        chain.append({"step": "定位授权角色", "detail": owner.code if owner else "-", "result": "allow"})
        return {"allowed": True, "code": code, "chain": chain, "permission": perm.code, "role": owner.code if owner else None}

    module = code.split(":", 1)[0] if ":" in code else code
    wildcard = f"{module}:*"
    if wildcard in user_permission_codes(user):
        chain.append({"step": "命中模块通配权限", "detail": wildcard, "result": "allow"})
        return {"allowed": True, "code": code, "chain": chain}

    chain.append({"step": "匹配权限点", "detail": f"未找到 {code}", "result": "deny"})
    return {"allowed": False, "code": code, "chain": chain}


# ------------------------------------------------------------------ 权限沙盘
def simulate_role_permission_change(role_id: int, add_codes: Iterable[str] = (), del_codes: Iterable[str] = ()) -> dict:
    """权限沙盘：预演一次角色权限变更的影响面，不落库。"""
    role = Role.objects.filter(id=role_id).first()
    if role is None:
        return {"error": "角色不存在"}

    add_codes, del_codes = set(add_codes or []), set(del_codes or [])
    current = set(
        Permission.objects.filter(rolepermission__role=role, is_deleted=False).values_list("code", flat=True)
    )
    final = (current | add_codes) - del_codes

    # 受影响用户：直接持有该角色的用户 + 继承了该角色的子角色用户
    child_ids = _descendant_role_ids(role)
    role_ids = {role.id} | child_ids
    user_ids = list(
        UserRole.objects.filter(role_id__in=role_ids).values_list("user_id", flat=True).distinct()
    )
    from .models import User

    users = list(User.objects.filter(id__in=user_ids).values("id", "username", "first_name", "dept__name"))

    # 菜单影响：菜单节点带 permission_code
    menus = Menu.objects.filter(is_deleted=False)
    menu_added = [{"code": m.code, "name": m.name} for m in menus if m.permission_code in (final - current)]
    menu_removed = [{"code": m.code, "name": m.name} for m in menus if m.permission_code in (current - final)]

    return {
        "role": {"id": role.id, "code": role.code, "name": role.name},
        "before": sorted(current),
        "after": sorted(final),
        "granted": sorted(add_codes & set(Permission.objects.filter(code__in=add_codes).values_list("code", flat=True))),
        "revoked": sorted(del_codes & current),
        "affected_user_count": len(users),
        "affected_users": users[:200],
        "affected_child_roles": sorted(child_ids),
        "menu_added": menu_added,
        "menu_removed": menu_removed,
        "api_perm_count": len(final),
        "generated_at": timezone.now().isoformat(),
    }


def _descendant_role_ids(role: Role) -> set:
    result, level, seen = set(), [role.id], {role.id}
    for _ in range(32):
        children = list(Role.objects.filter(parent_id__in=level, is_deleted=False).values_list("id", flat=True))
        children = [c for c in children if c not in seen]
        if not children:
            break
        seen.update(children)
        result.update(children)
        level = children
    return result


def apply_role_permission_change(role_id: int, add_codes=(), del_codes=(), operator=None) -> dict:
    """落库生效，并写入 PermissionChangeLog（含影响面报告），支持一键回滚。"""
    import uuid

    from .models import RolePermission

    report = simulate_role_permission_change(role_id, add_codes, del_codes)
    if "error" in report:
        return report

    role = Role.objects.get(id=role_id)
    batch_id = uuid.uuid4().hex[:16]

    for code in report["revoked"]:
        RolePermission.objects.filter(role=role, permission__code=code).delete()
    for code in add_codes:
        perm = Permission.objects.filter(code=code, is_deleted=False).first()
        if perm:
            RolePermission.objects.get_or_create(role=role, permission=perm)

    PermissionChangeLog.objects.create(
        batch_id=batch_id,
        change_type=(PermissionChangeLog.ChangeType.ROLE_PERM_DEL if report["revoked"] and not add_codes
                     else PermissionChangeLog.ChangeType.ROLE_PERM_ADD),
        target_type="role",
        target_id=role.id,
        before=report["before"],
        after=report["after"],
        impact=report,
        operator=operator if operator and operator.is_authenticated else None,
    )
    invalidate_user_permission_cache()
    return {"batch_id": batch_id, **report}


def rollback_permission_change(batch_id: str, operator=None) -> dict:
    """按批次号回滚权限变更。"""
    from .models import RolePermission

    logs = PermissionChangeLog.objects.filter(batch_id=batch_id, rolled_back=False)
    if not logs.exists():
        return {"error": "批次不存在或已回滚"}

    restored = []
    for log in logs:
        role = Role.objects.filter(id=log.target_id).first()
        if role is None:
            continue
        RolePermission.objects.filter(role=role).delete()
        for code in log.before or []:
            perm = Permission.objects.filter(code=code, is_deleted=False).first()
            if perm:
                RolePermission.objects.get_or_create(role=role, permission=perm)
        log.rolled_back = True
        log.save(update_fields=["rolled_back"])
        restored.append(role.code)

    PermissionChangeLog.objects.create(
        batch_id=f"rollback-{batch_id}",
        change_type=PermissionChangeLog.ChangeType.ROLLBACK,
        target_type="role",
        target_id=0,
        before={"batch": batch_id},
        after={"restored": restored},
        operator=operator if operator and operator.is_authenticated else None,
    )
    invalidate_user_permission_cache()
    return {"rolled_back": restored, "batch_id": batch_id}


def invalidate_user_permission_cache() -> None:
    """权限变更实时生效：自增版本戳，旧 key 自然失效。"""
    bump_perm_version()
    cache_delete_pattern("fn:")


# ------------------------------------------------------------------ 表达式校验
def check_expr(text: str) -> dict:
    ok, msg = validate_expr(text)
    return {"valid": ok, "message": msg}
