"""按角色联调：以各演示账号登录，访问其菜单应可达的接口，暴露 403/500。"""
import json
import os
import sys
import urllib.request
import urllib.error

# 登录接口要求图形验证码，而验证码明文只存在于服务端缓存里，
# 因此脚本需要引导 Django 才能从 cache 取到正确验证码（与 smoke.py 同法）。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from django.core.cache import cache  # noqa: E402

BASE = "http://127.0.0.1:8000"


def req(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw[:200]}
    except Exception as e:
        return -1, {"_err": repr(e)}


def login(username, password):
    """带图形验证码的登录：先取 captcha key，再从服务端缓存取明文验证码。"""
    st, j = req("GET", "/api/v1/accounts/auth/captcha/")
    if st != 200 or j.get("code") != 0:
        return st, j
    key = j["data"]["key"]
    code = cache.get(f"captcha:{key}")
    return req("POST", "/api/v1/accounts/auth/login/",
               {"username": username, "password": password, "captcha_key": key, "captcha_code": code})


COMMON = [
    ("GET", "/api/v1/accounts/auth/menus/"),
    ("GET", "/api/v1/accounts/auth/my_permissions/"),
    ("GET", "/api/v1/message/"),
    ("GET", "/api/v1/message/unread-count/"),
    ("GET", "/api/v1/workflow/instances/"),
    ("GET", "/api/v1/workflow/tasks/"),
    ("GET", "/api/v1/workflow/templates/"),
    ("GET", "/api/v1/attendance/records/"),
    ("GET", "/api/v1/attendance/punch/today/"),
    ("GET", "/api/v1/announcement/notices/"),
    ("GET", "/api/v1/document/docs/"),
    ("GET", "/api/v1/workflow/requests/"),
    ("GET", "/api/v1/meeting/rooms/"),
    ("GET", "/api/v1/meeting/bookings/"),
    ("GET", "/api/v1/meeting/minutes/"),
    ("GET", "/api/v1/schedule/tasks/"),
    ("GET", "/api/v1/schedule/schedules/"),
]
PER_ROLE = {
    "employee": [],
    "manager": [
        ("GET", "/api/v1/attendance/summary/dept/"),
        ("GET", "/api/v1/attendance/exceptions/"),
        ("GET", "/api/v1/workflow/requests/stats/"),
        ("GET", "/api/v1/insight/risk/"),
        ("GET", "/api/v1/insight/stats/"),
        ("GET", "/api/v1/insight/bottleneck/"),
        ("GET", "/api/v1/workflow/health/report/"),
        ("GET", "/api/v1/workflow/urges/"),
    ],
    "hr": [
        ("GET", "/api/v1/hr/staff/"),
        ("GET", "/api/v1/hr/transfers/"),
        ("GET", "/api/v1/hr/contracts/"),
        ("GET", "/api/v1/hr/trainings/"),
        ("GET", "/api/v1/hr/analytics/structure/"),
        ("GET", "/api/v1/accounts/users/"),
        ("GET", "/api/v1/attendance/summary/dept/"),
        ("GET", "/api/v1/attendance/exceptions/"),
    ],
    "finance": [
        ("GET", "/api/v1/workflow/requests/stats/"),
        ("GET", "/api/v1/workflow/requests/?status=approved"),
    ],
    "admin_staff": [
        ("GET", "/api/v1/announcement/notices/stats/"),
        ("GET", "/api/v1/accounts/system-params/"),
        ("GET", "/api/v1/meeting/rooms/"),
    ],
}
USERS = ["admin", "zhangwei", "lina", "wangfang", "liuyang", "chenjing", "zhaolei", "sunli"]

UNKNOWN = "<未知>"  # 无法推导权限码（路由不存在 / 方法不支持）


def perm_for(path, method="GET"):
    """复用 PermCodeMixin 的规则推导接口所需权限码，避免在脚本里重复维护一份映射。

    返回 None 表示该接口不校验权限码（仅需登录），UNKNOWN 表示无法推导。
    """
    try:
        from django.urls import resolve

        m = resolve(path)
        cls, actions = m.func.cls, m.func.actions
        action = actions.get(method.lower())
        if action is None:
            return UNKNOWN
        if action in (getattr(cls, "perm_map", None) or {}):
            return cls.perm_map[action]
        if action in (getattr(cls, "open_actions", None) or set()):
            return None
        prefix = getattr(cls, "perm_prefix", "")
        return f"{prefix}:{action}" if prefix else None
    except Exception:
        return UNKNOWN


def main():
    bad = 0
    for u in USERS:
        st, j = login(u, "Oa@123456")
        if st != 200 or j.get("code") != 0:
            print(f"[{u}] LOGIN FAIL {st} {j.get('msg')}")
            bad += 1
            continue
        tok = j["data"]["access"]
        roles, codes, is_super = None, set(), False
        st2, j2 = req("GET", "/api/v1/accounts/auth/my_permissions/", token=tok)
        if j2.get("code") == 0:
            roles = j2["data"].get("roles")
            codes = set(j2["data"].get("codes") or [])
            is_super = bool(j2["data"].get("is_superuser"))
        # menus: count visible pages
        stm, jm = req("GET", "/api/v1/accounts/auth/menus/", token=tok)
        menu_cnt = 0

        def count(nodes):
            c = 0
            for n in nodes or []:
                if n.get("type") == "menu":
                    c += 1
                c += count(n.get("children"))
            return c

        if jm.get("code") == 0:
            menu_cnt = count(jm.get("data"))
        eps = COMMON + PER_ROLE.get((roles or [""])[0], [])
        print(f"\n=== {u}  roles={roles}  pages={menu_cnt} ===")
        for method, p in eps:
            need = perm_for(p.split("?")[0], method)
            # 该角色是否本应有权访问：不校验权限 / 开放接口 / 权限码已授予
            should = is_super or need is None or (need != UNKNOWN and need in codes)
            st, j = req(method, p, token=tok)
            code = j.get("code") if isinstance(j, dict) else "-"
            got = st in (200, 201) and code == 0
            msg = (j.get("msg") or j.get("detail") or "") if isinstance(j, dict) else ""
            if need == UNKNOWN:
                bad += 1
                print(f"  !!! 路由不可解析 {method} {p} -> {st}")
            elif should and not got:
                bad += 1
                print(f"  !!! 应有权限却失败 {method} {p} -> {st} code={code} need={need} msg={msg}")
            elif not should and got:
                bad += 1
                print(f"  !!! 越权可访问     {method} {p} -> {st} need={need}")
    print(f"\nTOTAL PROBLEMS = {bad}")


if __name__ == "__main__":
    main()
