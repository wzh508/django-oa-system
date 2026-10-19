"""announcement / document / meeting / schedule 四模块 HTTP 冒烟测试。

以 admin(superuser) 身份走真实 JWT + DRF APIClient，验证路由注册、序列化、
权限码匹配与核心业务逻辑（会议室冲突检测、任务进度联动等）。
"""
import django
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import datetime

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

    # ---------------- announcement ----------------
    print("== announcement ==")
    r = c.post("/api/v1/announcement/notices/", {"title": "五一放假通知", "content": "放假三天",
                                                 "category": "notice", "level": "important"}, format="json")
    check("创建公告", created(r), f"-> {r.status_code}")
    aid = gid(r)
    r = c.get("/api/v1/announcement/notices/")
    check("公告列表", r.status_code == 200 and (r.data or {}).get("code") == 0)
    if aid:
        r = c.post(f"/api/v1/announcement/notices/{aid}/read/", {}, format="json")
        check("标记已读", r.status_code == 200)
    r = c.get("/api/v1/announcement/notices/stats/")
    check("阅读统计", r.status_code == 200 and "unread" in (r.data or {}).get("data", {}))

    # ---------------- document ----------------
    print("== document ==")
    r = c.post("/api/v1/document/docs/", {"name": "项目资料", "is_folder": True}, format="json")
    check("新建文件夹", created(r), f"-> {r.status_code}")
    fid = gid(r)
    f = SimpleUploadedFile("readme.txt", b"hello oa document", content_type="text/plain")
    r = c.post("/api/v1/document/docs/upload/", {"name": "readme.txt", "parent": fid or "",
             "share_type": "all", "file": f}, format="multipart")
    check("上传文件", created(r), f"-> {r.status_code}")
    did = gid(r)
    r = c.get("/api/v1/document/docs/")
    check("文档列表", r.status_code == 200 and (r.data or {}).get("code") == 0)
    if did:
        r = c.post(f"/api/v1/document/docs/{did}/share/", {"share_type": "dept"}, format="json")
        check("共享设置", r.status_code == 200)
        r = c.get(f"/api/v1/document/docs/{did}/download/")
        check("下载文件", r.status_code == 200, f"-> {r.status_code}")

    # ---------------- meeting ----------------
    print("== meeting ==")
    r = c.post("/api/v1/meeting/rooms/", {"name": "三楼大会议室", "capacity": 20, "location": "3F"}, format="json")
    check("创建会议室", created(r), f"-> {r.status_code}")
    rid = gid(r)
    now = timezone.now()
    start = (now + datetime.timedelta(hours=1)).isoformat()
    end = (now + datetime.timedelta(hours=2)).isoformat()
    payload = {"room": rid, "title": "周会", "start": start, "end": end, "attendee_ids": [user.id]}
    r = c.post("/api/v1/meeting/bookings/", payload, format="json")
    check("预约会议(无冲突)", created(r), f"-> {r.status_code}")
    bid = gid(r)
    r2 = c.post("/api/v1/meeting/bookings/", payload, format="json")
    check("冲突检测", r2.status_code == 400, f"-> {r2.status_code}")
    if bid:
        r = c.post(f"/api/v1/meeting/bookings/{bid}/cancel/", {}, format="json")
        check("取消预约", r.status_code == 200)
    r = c.post("/api/v1/meeting/minutes/", {"booking": bid, "title": "纪要1", "content": "讨论了X"}, format="json")
    check("创建纪要", created(r), f"-> {r.status_code}")

    # ---------------- schedule ----------------
    print("== schedule ==")
    r = c.post("/api/v1/schedule/schedules/", {"title": "客户拜访", "start": start, "end": end,
             "category": "meeting", "participant_ids": [user.id]}, format="json")
    check("创建日程", created(r), f"-> {r.status_code}")
    r = c.post("/api/v1/schedule/tasks/", {"title": "完成PRD", "priority": "high", "progress": 10}, format="json")
    check("创建任务", created(r), f"-> {r.status_code}")
    tid = gid(r)
    if tid:
        r = c.post(f"/api/v1/schedule/tasks/{tid}/progress/", {"progress": 100}, format="json")
        d = (r.data or {}).get("data", {})
        check("进度联动完成", r.status_code == 200 and d.get("status") == "done", f"-> {d}")

    print(f"\n==== 模块冒烟结果：{PASS} 通过 / {FAIL} 失败 ====")
    return FAIL


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
