"""站内消息通知统一入口。

各业务模块不得自行拼消息表，统一调用本模块。
"""
import logging

logger = logging.getLogger(__name__)


def notify_users(users, title: str, content: str, level: str = "info", biz_type: str = "", biz_id=None) -> int:
    """发送站内信，返回成功条数。消息模块不可用时降级为日志。"""
    count = 0
    try:
        from apps.message.models import Message

        for u in users:
            if u is None:
                continue
            Message.objects.create(
                recipient=u, title=title, content=content, level=level,
                biz_type=biz_type, biz_id=str(biz_id) if biz_id else "",
            )
            count += 1
    except Exception as exc:  # 消息表未就绪时不影响主流程
        logger.warning("notify fallback to log: %s | %s", title, exc)
    return count


def notify_user(user, title: str, content: str, **kwargs) -> int:
    return notify_users([user], title, content, **kwargs)
