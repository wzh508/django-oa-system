"""后端接口冒烟脚本（真实 HTTP 请求，非 mock）。

用法：
    python scripts/smoke.py [--base http://127.0.0.1:8000] [--password Oa@123456]
"""
import argparse
import os
import sys
import time

import httpx

# 让脚本能访问项目 settings 与缓存（验证码值从 Django 缓存读取，避免 pickle 解码问题）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from django.core.cache import cache  # noqa: E402

BASE_DEFAULT = "http://127.0.0.1:8000"
API = "/api/v1/accounts"

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(label, cond, detail=""):
    _results.append((label, cond, detail))
    print(f"  [{PASS if cond else FAIL}] {label} {detail}")
    return cond


def login(c, username, password):
    """登录并取 access token。"""
    cap = c.get(f"{API}/auth/captcha/").json()["data"]
    code = cache.get(f"captcha:{cap['key']}")
    r = c.post(f"{API}/auth/login/", json={"username": username, "password": password,
                                           "captcha_key": cap["key"], "captcha_code": code})
    body = r.json() if r.headers.get("content-type", "").find("json") >= 0 else {}
    return (body.get("data") or {}).get("access", ""), body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--password", default="Oa@123456")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    c = httpx.Client(base_url=base, timeout=20, trust_env=False)

    for _ in range(40):
        try:
            c.get("/api/schema/")
            break
        except Exception:
            time.sleep(1)
    else:
        print("服务未就绪")
        sys.exit(1)

    print("\n== 1. 验证码与登录 ==")
    r = c.get(f"{API}/auth/captcha/")
    d = r.json()["data"]
    check("GET captcha 图形验证码", r.status_code == 200 and d["image"].startswith("data:image/png"), f"key={d['key'][:8]}")
    code = cache.get(f"captcha:{d['key']}")
    check("验证码已入缓存", code is not None, f"code={code}")
    r = c.post(f"{API}/auth/login/", json={"username": "admin", "password": args.password,
                                           "captcha_key": d["key"], "captcha_code": code})
    body = r.json()
    check("POST login(admin)", r.status_code == 200 and body.get("code") == 0 and "access" in (body.get("data") or {}),
          f"status={r.status_code}")
    admin_tok = (body.get("data") or {}).get("access", "")
    H = {"Authorization": f"Bearer {admin_tok}"}

    print("\n== 2. 菜单与资料 ==")
    r = c.get(f"{API}/auth/menus/", headers=H)
    menus = r.json().get("data") or []
    count_menu = sum(len(m.get("children", [])) for m in menus)
    check("GET menus 动态菜单树", r.status_code == 200 and len(menus) >= 10, f"顶层{len(menus)}个 子项{count_menu}个")
    r = c.get(f"{API}/auth/my_permissions/", headers=H)
    codes = (r.json().get("data") or {}).get("codes", [])
    check("GET my-permissions", len(codes) >= 100, f"{len(codes)} 个权限码")
    r = c.get(f"{API}/auth/profile/", headers=H)
    check("GET profile", r.status_code == 200, "")

    print("\n== 3. 用户 / 角色 / 部门 ==")
    r = c.get(f"{API}/users/?page=1&page_size=5", headers=H)
    data = r.json().get("data") or {}
    check("GET users 统一分页", r.status_code == 200 and data.get("total", 0) >= 8,
          f"total={data.get('total')} list={len(data.get('list', []))}")
    r = c.get(f"{API}/departments/tree/", headers=H)
    check("GET departments/tree", r.status_code == 200 and len(r.json().get("data") or []) >= 1, "")
    r = c.get(f"{API}/roles/", headers=H)
    role_rows = r.json()["data"]["list"] if isinstance(r.json()["data"], dict) else r.json()["data"]
    check("GET roles", r.status_code == 200 and len(role_rows) >= 6, f"{len(role_rows)} 个角色")
    r = c.get(f"{API}/menus/tree/", headers=H)
    check("GET menus/tree", r.status_code == 200, "")

    print("\n== 4. 权限沙盘 ==")
    role_id = next(x["id"] for x in role_rows if x["code"] == "employee")
    r = c.post(f"{API}/permission-sandbox/simulate/", headers=H,
               json={"role_id": role_id, "add_codes": ["attendance:record:export"], "del_codes": ["workflow:instance:create"]})
    rep = r.json().get("data") or {}
    check("POST sandbox/simulate 影响面预演", r.status_code == 200 and rep.get("affected_user_count", 0) >= 1,
          f"受影响用户={rep.get('affected_user_count')} 新增菜单={len(rep.get('menu_added', []))} 失去菜单={len(rep.get('menu_removed', []))}")
    r = c.post(f"{API}/permission-sandbox/apply/", headers=H,
               json={"role_id": role_id, "add_codes": ["attendance:record:export"], "del_codes": [], "confirm": True})
    applied = r.json().get("data") or {}
    check("POST sandbox/apply 落库生效", r.status_code == 200 and applied.get("batch_id") is not None, "")
    r = c.post(f"{API}/permission-sandbox/rollback/", headers=H, json={"batch_id": applied.get("batch_id")})
    check("POST sandbox/rollback 一键回滚", r.status_code == 200, f"restored={(r.json().get('data') or {}).get('rolled_back')}")

    print("\n== 5. 决策可解释 ==")
    r = c.get(f"{API}/explain/permission/?code=attendance:record:export&user_id=3", headers=H)
    ed = r.json().get("data") or {}
    check("GET explain/permission 决策链", r.status_code == 200 and len(ed.get("chain", [])) >= 2,
          " -> ".join(x["step"] for x in ed.get("chain", [])))
    r = c.get(f"{API}/explain/data-scope/?resource=accounts.user&user_id=2", headers=H)
    sd = r.json().get("data") or {}
    check("GET explain/data-scope 决策链", r.status_code == 200 and len(sd.get("chain", [])) >= 2,
          f"表达式={sd.get('expression')}")

    print("\n== 6. 操作日志哈希链 ==")
    r = c.get(f"{API}/operation-logs/", headers=H)
    total = (r.json()["data"] or {}).get("total", 0) if isinstance(r.json().get("data"), dict) else 0
    check("GET operation-logs 写操作留痕", total >= 3, f"共 {total} 条")
    r = c.post(f"{API}/operation-logs/verify/", headers=H)
    v = r.json().get("data") or {}
    check("POST verify 未篡改时通过", v.get("ok") is True, f"total={v.get('total')} tampered={v.get('tampered_ids')}")

    print("\n== 7. 越权验证 ==")
    emp_tok, emp_body = login(c, "liuyang", args.password)
    check("普通员工登录", bool(emp_tok), "")
    EH = {"Authorization": f"Bearer {emp_tok}"}
    r = c.get(f"{API}/users/", headers=EH)
    check("员工访问用户管理应 403", r.status_code == 403, f"status={r.status_code} msg={(r.json() or {}).get('msg')}")
    r = c.get(f"{API}/auth/menus/", headers=EH)
    emp_menus = r.json().get("data") or []
    emp_count = sum(len(m.get("children", [])) for m in emp_menus)
    check("员工菜单少于管理员", emp_count < count_menu, f"员工{emp_count} vs 管理员{count_menu}")
    r = c.get(f"{API}/users/", headers={})
    check("未认证访问应 401", r.status_code == 401, f"status={r.status_code}")

    print("\n== 8. Swagger ==")
    paths = c.get("/api/schema/?format=json", timeout=30, headers={"Accept": "application/json"}).json().get("paths", {})
    check("OpenAPI 生成", len(paths) >= 20, f"{len(paths)} 个 path")

    ok_n = sum(1 for _, cond, _ in _results if cond)
    print(f"\n结果：{ok_n}/{len(_results)} 通过")
    sys.exit(0 if ok_n == len(_results) else 1)


if __name__ == "__main__":
    main()
