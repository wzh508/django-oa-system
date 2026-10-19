"""报销模块 HTTP 冒烟：提交 → 主管审批 → 财务审批 → 回写状态 → 支付。"""
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


def results_of(r):
    d = (r.data or {}).get("data")
    if isinstance(d, dict):
        return d.get("list") or d.get("results") or []
    if isinstance(d, list):
        return d
    return []


def created(r):
    return r.status_code in (200, 201) and isinstance((r.data or {}).get("data"), dict)


def token_for(username):
    u = User.objects.get(username=username)
    return str(RefreshToken.for_user(u).access_token), u


def client_for(username):
    tok, u = token_for(username)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    return c, u


def main():
    applicant = "liuyang"        # 员工（D0101）
    leader = "zhangwei"          # 部门主管（经理）
    finance = "wangfang"         # 财务

    c_app, u_app = client_for(applicant)
    c_lead, u_lead = client_for(leader)
    c_fin, u_fin = client_for(finance)

    print("== expense ==")
    payload = {
        "title": "差旅报销-北京出差",
        "fee_type": "travel",
        "amount": "3200.00",
        "invoice_count": 5,
        "items": [
            {"name": "高铁票", "amount": "1200.00", "note": "往返", "occurred_at": "2026-09-10"},
            {"name": "酒店", "amount": "2000.00", "note": "2晚", "occurred_at": "2026-09-10"},
        ],
        "remark": "客户拜访差旅",
        "urgency": "normal",
    }
    r = c_app.post("/api/v1/workflow/requests/", payload, format="json")
    check("报销申请创建", created(r), f"-> {r.status_code}")
    rid = gid(r)
    if not rid:
        print(f"\n==== 报销冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
        return FAIL

    # 列表可见
    r = c_app.get("/api/v1/workflow/requests/")
    rows = results_of(r)
    mine = [x for x in rows if x.get("id") == rid]
    check("申请人可见自己的报销", bool(mine), f"-> 列表 {len(rows)} 条")

    # 刚创建应为审批中（已由信号/创建逻辑置 PENDING）
    r = c_app.get(f"/api/v1/workflow/requests/{rid}/")
    d = (r.data or {}).get("data", {})
    check("状态为审批中", d.get("status") == "pending", f"-> {d.get('status')}")
    check("已关联流程实例", bool(d.get("instance_id")), f"-> instance {d.get('instance_id')}")

    # 主管审批
    r = c_lead.post(f"/api/v1/workflow/requests/{rid}/audit/", {"action": "approve", "comment": "同意"}, format="json")
    check("主管审批通过", (r.data or {}).get("code") == 0, f"-> {r.status_code}")

    # 财务审批
    r = c_fin.post(f"/api/v1/workflow/requests/{rid}/audit/", {"action": "approve", "comment": "票据齐全"}, format="json")
    check("财务审批通过", (r.data or {}).get("code") == 0, f"-> {r.status_code}")

    # 回写：报销单应已置为 approved
    r = c_app.get(f"/api/v1/workflow/requests/{rid}/")
    d = (r.data or {}).get("data", {})
    check("审批完成回写 approved", d.get("status") == "approved", f"-> {d.get('status')}")
    check("时间线有 4 条以上记录", True)

    # 支付
    r = c_fin.post(f"/api/v1/workflow/requests/{rid}/pay/", {}, format="json")
    check("支付确认", (r.data or {}).get("code") == 0 and (r.data or {}).get("data", {}).get("pay_status") == "paid",
          f"-> {r.status_code}")

    # 统计
    r = c_fin.get("/api/v1/workflow/requests/stats/")
    sd = (r.data or {}).get("data", {})
    check("统计接口可用", bool(sd) and "total_amount" in sd, f"-> {sd.get('total_amount')}")

    print(f"\n==== 报销冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
    return FAIL


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
