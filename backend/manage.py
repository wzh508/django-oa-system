#!/usr/bin/env python
"""Django 管理入口。

默认使用开发环境配置；生产用 DJANGO_SETTINGS_MODULE=config.settings.prod。
"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django 未安装，请先执行 scripts/bootstrap_env 安装依赖") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
