"""端到端联调：模拟前端登录后逐个调用页面依赖的接口，输出状态码与关键错误。"""
import json
import os
import sys
import urllib.request
import urllib.error

# 登录接口要求图形验证码，验证码明文只存在于服务端缓存，故先引导 Django（同 smoke.py）。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from django.core.cache import cache  # noqa: E402

BASE = "http://127.0.0.1:8000"
TOKEN = None


def req(method, path, body=None, anon=False):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if not anon and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        raw = resp.read().decode("utf-8", "replace")
        try:
            j = json.loads(raw)
        except Exception:
            j = {"_raw": raw[:200]}
        return resp.status, j
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(raw)
        except Exception:
            j = {"_raw": raw[:300]}
        return e.code, j
    except Exception as e:
        return -1, {"_err": repr(e)}


def login(username, password):
    """带图形验证码登录：先取 captcha key，再从服务端缓存取明文验证码。"""
    st, j = req("GET", "/api/v1/accounts/auth/captcha/")
    if st != 200 or j.get("code") != 0:
        return st, j
    key = j["data"]["key"]
    return req("POST", "/api/v1/accounts/auth/login/",
               {"username": username, "password": password,
                "captcha_key": key, "captcha_code": cache.get(f"captcha:{key}")})


def main():
    global TOKEN
    print("== 登录 ==")
    st, j = login("admin", "Oa@123456")
    print(st, j.get("msg"), "code=", j.get("code"))
    if st != 200 or j.get("code") != 0:
        print("LOGIN FAILED, stop")
        return
    data = j.get("data", {})
    TOKEN = data.get("access")
    print("  user:", data.get("user", {}).get("username"), "roles:", data.get("roles"))
    perms = data.get("permissions", [])
    print("  permissions count:", len(perms))

    print("== 用户信息/菜单/权限 ==")
    for p in ["/api/v1/accounts/auth/profile/", "/api/v1/accounts/auth/menus/",
              "/api/v1/accounts/auth/my_permissions/"]:
        st, j = req("GET", p)
        ok = j.get("code") == 0 if isinstance(j, dict) else False
        print(f"  {p} -> {st} code={j.get('code') if isinstance(j,dict) else '-'} ok={ok}")

    endpoints = [
        ("GET", "/api/v1/workflow/instances/"),
        ("GET", "/api/v1/workflow/tasks/?kind=todo"),
        ("GET", "/api/v1/workflow/tasks/?kind=done"),
        ("GET", "/api/v1/workflow/templates/"),
        ("GET", "/api/v1/workflow/templates/?code=expense"),
        ("GET", "/api/v1/workflow/instances/?page_size=3"),
        ("GET", "/api/v1/workflow/requests/"),
        ("GET", "/api/v1/workflow/requests/stats/"),
        ("GET", "/api/v1/insight/risk/"),
        ("GET", "/api/v1/insight/bottleneck/"),
        ("GET", "/api/v1/insight/stats/"),
        ("GET", "/api/v1/lowcode/schemas/"),
        ("GET", "/api/v1/lowcode/schemas/render/?code=satisfaction"),
        ("GET", "/api/v1/lowcode/records/"),
        ("GET", "/api/v1/message/"),
        ("GET", "/api/v1/message/unread-count/"),
        ("GET", "/api/v1/hr/staff/"),
        ("GET", "/api/v1/hr/analytics/structure/"),
        ("GET", "/api/v1/attendance/records/"),
        ("GET", "/api/v1/attendance/summary/monthly/"),
        ("GET", "/api/v1/attendance/summary/dept/"),
        ("GET", "/api/v1/announcement/notices/"),
        ("GET", "/api/v1/document/docs/"),
        ("GET", "/api/v1/meeting/rooms/"),
        ("GET", "/api/v1/schedule/schedules/"),
        ("GET", "/api/v1/accounts/users/"),
        ("GET", "/api/v1/accounts/roles/"),
        ("GET", "/api/v1/accounts/departments/"),
        ("GET", "/api/v1/accounts/data-scope-rules/"),
    ]
    print("== 业务接口 ==")
    bad = 0
    for method, p in endpoints:
        st, j = req(method, p)
        code = j.get("code") if isinstance(j, dict) else "-"
        ok = st in (200, 201) and code in (0, None, "")
        # 仅在失败时提取错误提示
        err = ""
        if not ok and isinstance(j, dict):
            err = j.get("msg") or j.get("detail") or json.dumps(j, ensure_ascii=False)[:150]
        if not ok:
            bad += 1
        flag = "OK " if ok else "!!!"
        extra = f"  err={err}" if err else ""
        print(f"  {flag} {method} {p} -> {st} code={code}{extra}")
    print(f"\n== 汇总：{len(endpoints) - bad}/{len(endpoints)} 正常，异常 {bad} 条 ==")


if __name__ == "__main__":
    main()
