"""审批流引擎端到端冒烟（真实 HTTP 请求）。

用法：
    python scripts/smoke_workflow.py [--base http://127.0.0.1:8000] [--password Oa@123456]
"""
import argparse
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()
from django.core.cache import cache  # noqa: E402

BASE = "http://127.0.0.1:8000"
API = "/api/v1/workflow"
_results = []


def check(label, cond, detail=""):
    _results.append((label, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")
    return cond


def login(c, username, password):
    cap = c.get("/api/v1/accounts/auth/captcha/").json()["data"]
    code = cache.get(f"captcha:{cap['key']}")
    r = c.post("/api/v1/accounts/auth/login/", json={"username": username, "password": password,
                                                     "captcha_key": cap["key"], "captcha_code": code})
    return (r.json().get("data") or {}).get("access", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--password", default="Oa@123456")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.base, timeout=30, trust_env=False)
    for _ in range(40):
        try:
            c.get("/api/schema/")
            break
        except Exception:
            time.sleep(1)

    print("\n== 1. 发起请假申请（days=5，触发条件分支） ==")
    tok = login(c, "liuyang", args.password)
    H = {"Authorization": f"Bearer {tok}"}
    r = c.post(f"{API}/instances/start/", headers=H, json={
        "template_code": "leave", "title": "年假申请 5 天", "category": "leave", "days": 5,
        "form_data": {"leave_type": "年假", "start_at": "2026-09-25", "end_at": "2026-09-29",
                      "days": 5, "reason": "家中有事"},
    })
    d = (r.json() if r.headers.get("content-type", "").find("json") >= 0 else {}).get("data") or {}
    check("POST instances/start", r.status_code == 200 and d.get("id"), f"单号={d.get('code')} 状态={d.get('status')}")
    inst_id = d.get("id")
    first_node = (d.get("flow_nodes") or [{}])[0]
    check("首个节点为直属主管审批", d.get("current_node_name") == "直属主管审批", f"当前节点={d.get('current_node_name')}")
    task_id = (d.get("tasks") or [{}])[0].get("id")
    assignee = (d.get("tasks") or [{}])[0].get("assignee_name")
    check("生成首个审批任务", bool(task_id), f"审批人={assignee}")

    print("\n== 2. 主管审批通过 → 引擎推进到下一节点 ==")
    tok2 = login(c, "zhangwei", args.password)
    H2 = {"Authorization": f"Bearer {tok2}"}
    r = c.post(f"{API}/tasks/{task_id}/act/", headers=H2, json={"action": "approve", "comment": "同意"})
    res = (r.json().get("data") or {}) if r.headers.get("content-type", "").find("json") >= 0 else {}
    check("POST tasks/{id}/act approve", r.status_code == 200 and res.get("result") == "advanced",
          f"推进到={res.get('next_node')}")
    r = c.get(f"{API}/instances/{inst_id}/", headers=H)
    d2 = r.json().get("data") or {}
    check("条件分支命中（days>3 → 部门负责人）", "部门负责人审批" in [n.get("name") for n in d2.get("flow_nodes", [])],
          f"当前节点={d2.get('current_node_name')}")
    check("审批历史留痕", len(d2.get("records", [])) >= 2, f"{len(d2.get('records', []))} 条记录")

    print("\n== 3. 并发重复审批应被拒绝 ==")
    r = c.post(f"{API}/tasks/{task_id}/act/", headers=H2, json={"action": "approve", "comment": "重复提交"})
    check("重复审批返回 409", r.status_code == 409, f"status={r.status_code} msg={(r.json() or {}).get('msg')}")

    print("\n== 4. 非审批人操作应被拒绝 ==")
    pending_task = next((t for t in d2.get("tasks", []) if t.get("status") == "pending"), None)
    if pending_task:
        r = c.post(f"{API}/tasks/{pending_task['id']}/act/", headers=H, json={"action": "approve"})
        check("非审批人审批应 403", r.status_code == 403, f"status={r.status_code}")

    print("\n== 5. 撤回（仅发起人、当前节点未处理） ==")
    r = c.post(f"{API}/instances/{inst_id}/revoke/", headers=H, json={"comment": "临时取消"})
    check("POST instances/{id}/revoke", r.status_code == 200, f"status={r.status_code}")
    r = c.get(f"{API}/instances/{inst_id}/", headers=H)
    check("状态变为已撤回", (r.json().get("data") or {}).get("status") == "revoked", "")

    admin_tok = login(c, "admin", args.password)
    HA = {"Authorization": f"Bearer {admin_tok}"}

    print("\n== 6. 模板版本快照隔离（创新点 6.2） ==")
    r = c.get(f"{API}/templates/?code=leave", headers=H)
    tpls = r.json()["data"]["list"] if isinstance(r.json()["data"], dict) else r.json()["data"]
    tpl = next(t for t in tpls if t["is_active"])
    before_snapshot = (c.post(f"{API}/instances/start/", headers=H, json={
        "template_code": "leave", "title": "快照隔离测试单", "category": "leave", "days": 1,
        "form_data": {"days": 1}}).json().get("data") or {})
    inst2_id = before_snapshot.get("id")
    before_nodes = [n["name"] for n in before_snapshot.get("flow_nodes", [])]
    before_version = before_snapshot.get("template_version")

    # 修改模板：删除 HR 复核节点后重新发布
    r = c.get(f"{API}/templates/{tpl['id']}/", headers=HA)
    nodes = [n for n in r.json()["data"].get("nodes", []) if n["name"] != "HR复核"]
    r = c.put(f"{API}/templates/{tpl['id']}/", headers=HA, json={
        "code": "leave", "name": "请假申请", "category": "leave",
        "form_schema": r.json()["data"].get("form_schema", []),
        "nodes": [{k: v for k, v in n.items() if k not in ("id",)} for n in nodes]})
    check("修改模板节点", r.status_code in (200, 201), f"status={r.status_code}")
    r = c.post(f"{API}/templates/{tpl['id']}/publish/", headers=HA)
    check("发布新版本", r.status_code == 200 and (r.json().get("data") or {}).get("version") == tpl["version"] + 1,
          f"version={(r.json().get('data') or {}).get('version')}")

    r = c.get(f"{API}/instances/{inst2_id}/", headers=H)
    after = r.json().get("data") or {}
    after_nodes = [n["name"] for n in after.get("flow_nodes", [])]
    check("在途单据节点序列不变", after_nodes == before_nodes,
          f"改前={before_nodes} 改后={after_nodes}")
    check("在途单据模板版本不变", after.get("template_version") == before_version,
          f"v{before_version} → v{after.get('template_version')}")

    print("\n== 7. 新单据使用新模板 ==")
    new_inst = (c.post(f"{API}/instances/start/", headers=H, json={
        "template_code": "leave", "title": "新模板验证单", "category": "leave", "days": 1,
        "form_data": {"days": 1}}).json().get("data") or {})
    check("新单据使用新版本", new_inst.get("template_version") == tpl["version"] + 1,
          f"version={new_inst.get('template_version')}")
    check("新单据节点已变化", "HR复核" not in [n["name"] for n in new_inst.get("flow_nodes", [])],
          f"节点={[n['name'] for n in new_inst.get('flow_nodes', [])]}")

    print("\n== 8. 待办 / 已办 ==")
    r = c.get(f"{API}/tasks/?kind=todo", headers=H2)
    todo = (r.json()["data"] or {}).get("total", 0) if isinstance(r.json()["data"], dict) else 0
    check("GET tasks?kind=todo", r.status_code == 200, f"待办 {todo} 条")
    r = c.get(f"{API}/tasks/?kind=done", headers=H2)
    check("GET tasks?kind=done", r.status_code == 200, "")

    print("\n== 9. 流程健康度与沙盘回放 ==")
    r = c.get(f"{API}/health/report/", headers=HA)
    hd = r.json().get("data") or {}
    check("GET health/report", r.status_code == 200 and "nodes" in hd, f"节点 {len(hd.get('nodes', []))} 个")
    r = c.get(f"{API}/templates/?code=expense", headers=HA)
    rows2 = r.json()["data"]["list"] if isinstance(r.json()["data"], dict) else r.json()["data"]
    tpl_expense = next(t for t in rows2 if t["is_active"])
    r = c.post(f"{API}/replay/run/", headers=HA,
               json={"template_id": tpl_expense["id"], "since_days": 90, "limit": 500})
    rp = r.json().get("data") or {}
    report = rp.get("result", {})
    check("POST replay/run", r.status_code == 200 and rp.get("status") == "success",
          f"样本={report.get('sample_count')} 耗时={rp.get('cost_ms')}ms")
    check("回放样本 >= 20 条", (report.get("sample_count") or 0) >= 20, f"{report.get('sample_count')} 条")
    check("回放输出瓶颈 TOP3", len(report.get("bottleneck_top3", [])) == 3,
          f"瓶颈={[b['node'] for b in report.get('bottleneck_top3', [])]}")
    check("回放给出优化建议", len(report.get("advice", [])) >= 2, f"{len(report.get('advice', []))} 条建议")
    check("回放耗时 <= 30s", (rp.get("cost_ms") or 0) <= 30000, f"{rp.get('cost_ms')}ms")

    ok_n = sum(1 for _, x in _results if x)
    print(f"\n结果：{ok_n}/{len(_results)} 通过")
    sys.exit(0 if ok_n == len(_results) else 1)


if __name__ == "__main__":
    main()
