"""以 gunicorn 启动生产 HTTP 服务（跨平台，避免 Windows 下可执行文件路径问题）。

    python manage.py run_gunicorn [port]   # 默认 8000
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "以 gunicorn 启动生产 HTTP 服务（config.wsgi:application）"

    def add_arguments(self, parser):
        parser.add_argument("port", nargs="?", default="8000", help="监听端口，默认 8000")
        parser.add_argument("--workers", default="4", help="worker 数量，默认 4")

    def handle(self, *args, **opts):
        try:
            from gunicorn.app.wsgiapp import WSGIApplication
        except ImportError:
            self.stderr.write("未安装 gunicorn，请先 `pip install gunicorn` 或使用 runserver。")
            return

        port = opts["port"]
        workers = opts["workers"]
        self.stdout.write(f"==> gunicorn 启动 config.wsgi:application :{port} workers={workers}")
        WSGIApplication([
            "config.wsgi:application",
            "-b", f"0.0.0.0:{port}",
            "-w", str(workers),
            "--timeout", "120",
            "--access-logfile", "-",
            "--error-logfile", "-",
        ]).run()
