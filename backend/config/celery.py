"""Celery 配置。Redis 不可用时可降级为 filesystem broker。"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("oa")

_BROKER_BACKEND = os.environ.get("CELERY_BROKER_BACKEND", "redis").lower()
if _BROKER_BACKEND == "filesystem":
    from config.settings.base import BASE_DIR, CELERY_FILESYSTEM_PATH

    os.makedirs(CELERY_FILESYSTEM_PATH, exist_ok=True)
    os.makedirs(os.path.join(CELERY_FILESYSTEM_PATH, "processed"), exist_ok=True)
    app.conf.broker_url = "filesystem://"
    app.conf.broker_transport_options = {
        "data_folder_in": CELERY_FILESYSTEM_PATH,
        "data_folder_out": CELERY_FILESYSTEM_PATH,
        "processed_folder": os.path.join(CELERY_FILESYSTEM_PATH, "processed"),
        "store_processed": True,
    }
else:
    app.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")

app.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")
app.conf.timezone = "Asia/Shanghai"
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.worker_hijack_root_logger = False
app.conf.beat_schedule = {
    "recompute-sla-prediction-daily": {
        "task": "apps.insight.tasks.recompute_predictions",
        "schedule": 3600.0,  # 每小时重算一次高风险单据
    },
    "smart-urge-scan": {
        "task": "apps.insight.tasks.scan_and_urge",
        "schedule": 1800.0,  # 每 30 分钟扫描一次待催办单据
    },
}
app.autodiscover_tasks()
