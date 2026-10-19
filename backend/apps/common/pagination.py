"""统一分页响应：{list, total, page, page_size}。"""
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    page_query_param = "page"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("code", 0),
                    ("msg", "ok"),
                    (
                        "data",
                        OrderedDict(
                            [
                                ("list", data),
                                ("total", self.page.paginator.count),
                                ("page", self.page.number),
                                ("page_size", self.get_page_size(self.request)),
                            ]
                        ),
                    ),
                ]
            )
        )


class NoPagination(PageNumberPagination):
    """用于下拉/全量接口。"""

    page_size = None
