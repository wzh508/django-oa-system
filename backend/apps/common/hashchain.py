"""操作日志哈希链：任何一条被篡改都能被链式校验定位。

curr_hash = SHA256(prev_hash + 规范化内容)
"""
import hashlib
import json
from typing import Any

GENESIS_HASH = "0" * 64


def canonical(record: dict) -> str:
    """规范化：固定键序、去掉 None、UTF-8，保证同一内容永远得到同一哈希。"""
    clean = {k: v for k, v in record.items() if v is not None}
    return json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_hash(prev_hash: str, record: dict) -> str:
    payload = f"{prev_hash}|{canonical(record)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_record(prev_hash: str, **fields: Any) -> tuple:
    """返回 (curr_hash, canonical_content)。"""
    return compute_hash(prev_hash, fields), canonical(fields)


def verify_chain(rows) -> dict:
    """rows: 按 id 升序、含 prev_hash / curr_hash / content 的可迭代对象。

    返回 {"ok": bool, "total": n, "tampered_ids": [...], "broken_at": id|None}
    """
    total = 0
    tampered: list = []
    broken_at = None
    prev = GENESIS_HASH

    for idx, row in enumerate(rows):
        total += 1
        rec_prev = row["prev_hash"] or GENESIS_HASH
        expected_prev = prev
        try:
            content = canonical(json.loads(row["content"])) if isinstance(row["content"], str) else canonical(row["content"])
            expected_hash = compute_hash(rec_prev, json.loads(row["content"]) if isinstance(row["content"], str) else row["content"])
        except Exception:
            tampered.append(row["id"])
            broken_at = row["id"] if broken_at is None else broken_at
            prev = row["curr_hash"]
            continue

        if rec_prev != expected_prev or row["curr_hash"] != expected_hash:
            tampered.append(row["id"])
            if broken_at is None:
                broken_at = row["id"]
        prev = row["curr_hash"]

    return {"ok": not tampered, "total": total, "tampered_ids": tampered, "broken_at": broken_at}
