"""insight 模块 HTTP 冒烟：时效预测、风险看板、瓶颈分析、分级催办。"""
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


def main():
    u = User.objects.get(username="admin")
    tok = str(RefreshToken.for_user(u).access_token)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")

    print("== insight ==")
    r = c.post("/api/v1/insight/refresh/")
    d = (r.data or {}).get("data", {})
    check("重算时效预测", (r.data or {}).get("code") == 0 and d.get("predicted", 0) >= 0, f"-> {d}")

    r = c.get("/api/v1/insight/risk/")
    rd = (r.data or {}).get("data", {})
    check("风险看板可用", (r.data or {}).get("code") == 0 and "distribution" in rd, f"-> {rd.get('distribution')}")

    r = c.get("/api/v1/insight/bottleneck/")
    bd = (r.data or {}).get("data", {})
    check("瓶颈分析可用", (r.data or {}).get("code") == 0 and "top3" in bd, f"-> {bd.get('top3')}")

    r = c.get("/api/v1/insight/stats/")
    sd = (r.data or {}).get("data", {})
    check("时效统计可用", (r.data or {}).get("code") == 0 and "avg_hours" in sd, f"-> {sd}")

    r = c.post("/api/v1/insight/urge/", {"warning_hours": 24, "overdue_threshold_hours": 0})
    ud = (r.data or {}).get("data", {})
    check("分级催办执行", (r.data or {}).get("code") == 0 and "total" in ud, f"-> {ud}")

    print(f"\n==== insight 冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
    return FAIL


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
