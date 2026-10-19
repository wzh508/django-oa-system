"""lowcode 模块 HTTP 冒烟：schema 增改发布、渲染、动态数据提交与查询。"""
import django
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name} {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def created(r):
    return r.status_code in (200, 201) and isinstance((r.data or {}).get("data"), dict)


def gid(r):
    d = (r.data or {}).get("data")
    return d.get("id") if isinstance(d, dict) else None


def main():
    admin = User.objects.get(username="admin")
    tok = str(RefreshToken.for_user(admin).access_token)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")

    # 幂等：先清理上次遗留的冒烟数据，避免 (code, version) 唯一冲突
    from apps.lowcode.models import DynamicRecord, FormSchema

    FormSchema.objects.filter(code="smoke_form").delete()
    DynamicRecord.objects.filter(form_code="smoke_form").delete()

    print("== lowcode ==")
    r = c.post("/api/v1/lowcode/schemas/", {
        "code": "smoke_form", "name": "冒烟表单", "category": "test", "status": "draft",
        "fields": [{"key": "a", "label": "字段A", "type": "text", "required": True, "col": 12}],
    }, format="json")
    check("创建表单", created(r), f"-> {r.status_code}")
    fid = gid(r)
    if not fid:
        print(f"\n==== lowcode 冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
        return FAIL

    r = c.post(f"/api/v1/lowcode/schemas/{fid}/publish/", {}, format="json")
    check("发布表单", (r.data or {}).get("code") == 0 and (r.data or {}).get("data", {}).get("status") == "published",
          f"-> {r.status_code}")

    r = c.get("/api/v1/lowcode/schemas/render/?code=smoke_form")
    check("按编码渲染已发布表单", (r.data or {}).get("code") == 0 and (r.data or {}).get("data", {}).get("code") == "smoke_form",
          f"-> {r.status_code}")

    # 员工提交动态数据
    emp = User.objects.get(username="liuyang")
    tok2 = str(RefreshToken.for_user(emp).access_token)
    c2 = APIClient()
    c2.credentials(HTTP_AUTHORIZATION=f"Bearer {tok2}")
    r = c2.post("/api/v1/lowcode/records/", {"form": fid, "form_data": {"a": "hello"}}, format="json")
    check("提交动态数据", created(r), f"-> {r.status_code}")
    rid = gid(r)

    r = c2.get("/api/v1/lowcode/records/")
    rows = ((r.data or {}).get("data") or {})
    rows = rows.get("list") if isinstance(rows, dict) else rows
    mine = [x for x in rows if x.get("id") == rid]
    check("提交人可查到自己的数据", bool(mine), f"-> {len(rows)} 条")

    r = c.get("/api/v1/lowcode/schemas/")
    check("管理员可见表单列表", (r.data or {}).get("code") == 0, f"-> {r.status_code}")

    print(f"\n==== lowcode 冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
    return FAIL


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
