"""请求日志中间件：注入 request_id 并记录访问耗时。"""
import logging
import time
import uuid

logger = logging.getLogger("oa.access")


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex
        request._start_at = time.time()
        response = self.get_response(request)
        cost = int((time.time() - getattr(request, "_start_at", time.time())) * 1000)
        logger.info(
            "%s %s -> %s (%sms) rid=%s",
            request.method,
            request.path,
            getattr(response, "status_code", "-"),
            cost,
            request.request_id,
        )
        response["X-Request-ID"] = request.request_id
        return response
