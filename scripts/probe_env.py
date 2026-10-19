# -*- coding: utf-8 -*-
"""环境探测脚本（临时用，后续并入 bootstrap_env）"""
import ctypes
import json
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

R = {}


def which(name):
    return shutil.which(name) or ""


def run(cmd, timeout=10):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           shell=True, encoding="utf-8", errors="ignore")
        return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else ""
    except Exception as e:
        return "ERR:%s" % type(e).__name__


R["os"] = platform.platform()
R["arch"] = platform.architecture()[0]
R["is_admin"] = ctypes.windll.shell32.IsUserAnAdmin() != 0
R["cpu_count"] = __import__("os").cpu_count()

for d in ("C:/", "D:/"):
    try:
        t, u, f = shutil.disk_usage(d)
        R["disk_" + d[0]] = "total=%.1fGB free=%.1fGB" % (t / 2 ** 30, f / 2 ** 30)
    except Exception as e:
        R["disk_" + d[0]] = "NA (%s)" % e

try:
    import ctypes as _c

    class MEM(_c.Structure):
        _fields_ = [("dwLength", _c.c_ulong), ("dwMemoryLoad", _c.c_ulong),
                    ("ullTotalPhys", _c.c_ulonglong), ("ullAvailPhys", _c.c_ulonglong),
                    ("ullTotalPageFile", _c.c_ulonglong), ("ullAvailPageFile", _c.c_ulonglong),
                    ("ullTotalVirtual", _c.c_ulonglong), ("ullAvailVirtual", _c.c_ulonglong),
                    ("ullAvailExtendedVirtual", _c.c_ulonglong)]

    m = MEM()
    m.dwLength = _c.sizeof(MEM)
    _c.windll.kernel32.GlobalMemoryStatusEx(_c.byref(m))
    R["mem"] = "total=%.1fGB avail=%.1fGB" % (m.ullTotalPhys / 2 ** 30, m.ullAvailPhys / 2 ** 30)
except Exception as e:
    R["mem"] = "NA (%s)" % e

TOOLS = ["python", "py", "pip", "node", "npm", "pnpm", "git", "winget", "choco", "scoop",
         "docker", "mysql", "mysqld", "mysqlsh", "redis-server", "redis-cli"]
for t in TOOLS:
    R["which_" + t] = which(t)

VER = {"python": "python --version", "py": "py -0p", "pip": "pip --version",
       "node": "node -v", "npm": "npm -v", "git": "git --version",
       "winget": "winget --version", "docker": "docker --version",
       "mysql": "mysql --version", "mysqld": "mysqld --version",
       "redis-server": "redis-server --version"}
for k, c in VER.items():
    R["ver_" + k] = run(c)

# 端口占用
for port in (3306, 6379, 8000, 5173, 8080, 80):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        R["port_%d" % port] = "LISTEN"
    except Exception:
        R["port_%d" % port] = "free"
    finally:
        s.close()

# MySQL 服务
R["svc_mysql"] = run('powershell -NoProfile -Command "(Get-Service | Where-Object {$_.Name -like \'*mysql*\'} | ForEach-Object {$_.Name+\'=\'+$_.Status}) -join \';\'"', 25)
R["svc_redis"] = run('powershell -NoProfile -Command "(Get-Service | Where-Object {$_.Name -like \'*redis*\'} | ForEach-Object {$_.Name+\'=\'+$_.Status}) -join \';\'"', 25)

# 网络连通性
NET = {
    "pypi_official": "https://pypi.org/simple/",
    "pypi_tuna": "https://pypi.tuna.tsinghua.edu.cn/simple/",
    "npm_npmmirror": "https://registry.npmmirror.com/",
    "npm_official": "https://registry.npmjs.org/",
    "github": "https://github.com/",
}
for k, u in NET.items():
    t0 = time.time()
    try:
        urllib.request.urlopen(u, timeout=5)
        R["net_" + k] = "OK %.2fs" % (time.time() - t0)
    except Exception as e:
        R["net_" + k] = "FAIL %s" % type(e).__name__

R["py_exe"] = sys.executable
R["py_ver"] = sys.version.split()[0]
R["pip_config"] = run("pip config list")

print(json.dumps(R, ensure_ascii=False, indent=2))
