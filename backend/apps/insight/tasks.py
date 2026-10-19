"""insight 定时任务入口。

`config/celery.py` 的 `beat_schedule` 声明了两个周期任务：
    apps.insight.tasks.recompute_predictions  （每小时重算时效预测）
    apps.insight.tasks.scan_and_urge          （每 30 分钟扫描待催办单据）

但此前本模块并不存在，celery beat 一启动就会报 unregistered task，
时效预测与智能催办永远不会按计划执行。这里补上入口，
任务体只做薄封装，逻辑复用 `services`，保证「定时触发」与「HTTP 手动触发」
走的是同一份实现（`/insight/refresh/`、`/insight/urge/`）。
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.insight.tasks.recompute_predictions")
def recompute_predictions() -> int:
    """重算所有在途单据的时效预测并落库，返回条数。"""
    from . import services

    count = services.refresh_predictions()
    logger.info("时效预测已重算：%s 条", count)
    return count


@shared_task(name="apps.insight.tasks.scan_and_urge")
def scan_and_urge() -> dict:
    """扫描临期/超时任务并按风险分级催办。"""
    from . import services

    result = services.graded_urge()
    logger.info("智能催办扫描完成：%s", result)
    return result
