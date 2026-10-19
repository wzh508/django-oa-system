"""HR 模块 HTTP 冒烟测试。"""
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


def gid(r):
    d = (r.data or {}).get("data")
    return d.get("id") if isinstance(d, dict) else None


def created(r):
    return r.status_code in (200, 201) and isinstance((r.data or {}).get("data"), dict)


def main():
    user = User.objects.get(username="admin")
    access = str(RefreshToken.for_user(user).access_token)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    print("== hr ==")
    r = c.get("/api/v1/hr/staff/")
    check("员工档案列表", r.status_code == 200 and (r.data or {}).get("code") == 0)
    lst = ((r.data or {}).get("data") or [])
    sid = lst[0]["id"] if isinstance(lst, list) and lst else None
    if sid:
        r = c.put(f"/api/v1/hr/staff/{sid}/", {"education": "硕士"}, format="json")
        check("更新档案", r.status_code in (200, 201), f"-> {r.status_code}")

    r = c.post("/api/v1/hr/transfers/", {"employee": user.id, "type": "transfer",
             "to_dept": 1, "effective_date": "2026-10-01", "remark": "调动"}, format="json")
    check("入转调离创建", created(r), f"-> {r.status_code}")

    r = c.post("/api/v1/hr/contracts/", {"employee": user.id, "contract_type": "fixed",
             "status": "active", "salary": "15000.00"}, format="json")
    check("合同创建", created(r), f"-> {r.status_code}")
    cid = gid(r)
    if cid:
        r = c.patch(f"/api/v1/hr/contracts/{cid}/", {"status": "active"}, format="json")
        check("合同更新", r.status_code in (200, 201))
        r = c.delete(f"/api/v1/hr/contracts/{cid}/")
        check("合同删除", r.status_code in (200, 204))

    r = c.post("/api/v1/hr/trainings/", {"employee": user.id, "title": "管理培训",
             "organization": "外部机构", "hours": 16, "score": "优秀"}, format="json")
    check("培训创建", created(r), f"-> {r.status_code}")

    r = c.get("/api/v1/hr/analytics/structure/")
    d = (r.data or {}).get("data", {})
    check("员工结构分析", r.status_code == 200 and "total" in d and d.get("total") > 0, f"-> {d.get('total')}")

    print(f"\n==== HR 冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
    return FAIL


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
