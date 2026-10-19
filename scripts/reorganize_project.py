#!/usr/bin/env python
"""将 D:\\project 重组为 前端 / 后端 / MySQL 三个部分。

设计要点：
1. 同盘符移动使用 os.rename，是 O(1) 的目录项操作，不会真正拷贝 83MB 的 .venv。
2. 移动前先把待变更文件复制到 .backup/<日期>/，保证可回滚。
3. venv 移动后 Scripts/activate* 里的 VIRTUAL_ENV 硬编码路径会失效，需要同步改写。

用法：
    python scripts/reorganize_project.py --apply     # 实际执行
    python scripts/reorganize_project.py             # 仅打印计划（dry-run）
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(r"D:\project")
BACKUP_ROOT = ROOT / ".backup" / date.today().isoformat()

# 虚拟环境 / 生成物：备份时跳过，避免无意义的 83MB 拷贝
SKIP_IN_BACKUP = {".venv", "node_modules", "__pycache__", ".pytest_cache", "dist", ".git"}


def plan_moves() -> list[tuple[Path, Path, str]]:
    """返回 (源路径, 目标路径, 说明) 列表。"""
    moves: list[tuple[Path, Path, str]] = []

    # 1) db/*.sql  ->  mysql/
    db_dir = ROOT / "db"
    if db_dir.is_dir():
        for sql in sorted(db_dir.glob("*.sql")):
            moves.append((sql, ROOT / "mysql" / sql.name, "MySQL 脚本归入 mysql/"))

    # 2) backend/_* 调试残留 -> backend/_tmp/
    backend = ROOT / "backend"
    tmp_dir = backend / "_tmp"
    for f in sorted(backend.glob("_*")):
        if f.is_file():
            moves.append((f, tmp_dir / f.name, "调试残留归档到 backend/_tmp/"))

    # 3) fastapi-skeleton -> backend/fastapi-skeleton（归入后端）
    skel = ROOT / "fastapi-skeleton"
    if skel.is_dir() and not (backend / "fastapi-skeleton").exists():
        moves.append((skel, backend / "fastapi-skeleton", "第二套 FastAPI 后端归入 backend/"))

    return moves


def backup(moves: list[tuple[Path, Path, str]]) -> None:
    """把待变更内容复制到 .backup/<日期>/，排除虚拟环境与生成物。"""
    print(f"[backup] 目标: {BACKUP_ROOT}")
    for src, _dst, _note in moves:
        if not src.exists():
            continue
        if src.is_file():
            dst = BACKUP_ROOT / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        else:
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d not in SKIP_IN_BACKUP]
                rel_root = Path(root).relative_to(ROOT)
                for fn in files:
                    s = Path(root) / fn
                    d = BACKUP_ROOT / rel_root / fn
                    d.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(s, d)
                    except OSError as exc:  # 长路径 / 占用文件不应中断整体备份
                        print(f"  [warn] 备份失败 {s}: {exc}")
    print("[backup] 完成")


def apply_moves(moves: list[tuple[Path, Path, str]]) -> None:
    """执行移动，全部使用 os.rename（同盘 O(1)）。"""
    for src, dst, note in moves:
        if not src.exists():
            print(f"  [skip] 源不存在: {src}")
            continue
        if dst.exists():
            print(f"  [skip] 目标已存在: {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.rename(src, dst)  # 同盘移动 = 目录项重命名，不拷贝数据
            print(f"  [move] {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}  ({note})")
        except OSError as exc:
            print(f"  [fail] {src} -> {dst}: {exc}", file=sys.stderr)


def fix_venv_activation(venv_root: Path) -> None:
    """改写 venv 激活脚本中的 VIRTUAL_ENV 硬编码路径。

    Windows venv 的 python.exe 依赖 pyvenv.cfg 的 home（指向系统解释器，移动后仍有效），
    但 activate 脚本里的 VIRTUAL_ENV 是绝对路径，必须重写，否则 activate 后路径错乱。
    """
    if not venv_root.is_dir():
        return
    scripts = venv_root / "Scripts"
    if not scripts.is_dir():
        return
    for name in ("activate.bat", "Activate.ps1", "activate"):
        f = scripts / name
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        old_posix = str(venv_root).replace("\\", "/")
        # 备份里记录的是移动前路径：fastapi-skeleton/.venv
        legacy = str(ROOT / "fastapi-skeleton" / ".venv")
        new = text.replace(legacy, str(venv_root)).replace(legacy.replace("\\", "/"), old_posix)
        # 兼容其它可能的写法
        new = new.replace("D:/project/fastapi-skeleton/.venv", old_posix)
        if new != text:
            f.write_text(new, encoding="utf-8")
            print(f"  [fix] 已修正 {f.relative_to(ROOT)} 中的 VIRTUAL_ENV 路径")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际执行；不加则只打印计划")
    args = ap.parse_args()

    moves = plan_moves()
    print(f"共 {len(moves)} 项变更计划：")
    for src, dst, note in moves:
        print(f"  {src.relative_to(ROOT)}  ->  {dst.relative_to(ROOT)}   # {note}")

    if not args.apply:
        print("\n[dry-run] 未做任何修改。加 --apply 执行。")
        return 0

    print("\n开始执行...")
    backup(moves)
    apply_moves(moves)

    # SQL 搬空后移除空的 db 目录；rmdir 只删空目录，非空会抛错，天然安全
    db_dir = ROOT / "db"
    if db_dir.is_dir() and not any(db_dir.iterdir()):
        db_dir.rmdir()
        print("  [rmdir] 已移除空的 db/ 目录")

    fix_venv_activation(ROOT / "backend" / "fastapi-skeleton" / ".venv")
    print("\n完成。如需回滚，从 " + str(BACKUP_ROOT) + " 复制回对应位置即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
