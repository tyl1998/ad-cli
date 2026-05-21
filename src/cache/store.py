"""元素坐标缓存 — SQLite 存储 (~/.ad-cli/cache/elements.db)

Schema:
    element_cache(package, activity, app_version, query, query_type,
                  center_x, center_y, bounds, hit_count, last_seen_ts, source_exec)

TTL 失效规则（双重校验）：
    1. app_version 不匹配 → 立即失效
    2. 超过 ttl_days → 失效
    3. hit_count < confidence_threshold → 不信任（不算失效，仍然积累）
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

_DB_PATH = Path.home() / ".ad-cli" / "cache" / "elements.db"

_DDL = """
CREATE TABLE IF NOT EXISTS element_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    package       TEXT    NOT NULL,
    activity      TEXT    NOT NULL,
    app_version   TEXT    NOT NULL DEFAULT '',
    query         TEXT    NOT NULL,
    query_type    TEXT    NOT NULL,
    center_x      INTEGER NOT NULL,
    center_y      INTEGER NOT NULL,
    bounds        TEXT,
    hit_count     INTEGER NOT NULL DEFAULT 1,
    last_seen_ts  INTEGER NOT NULL,
    source_exec   TEXT,
    page_hash     TEXT,               -- pHash hex，仅 query_type='label' 时使用
    UNIQUE(package, activity, app_version, query, query_type)
);
CREATE INDEX IF NOT EXISTS idx_lookup
    ON element_cache(package, activity, app_version, query);
CREATE INDEX IF NOT EXISTS idx_label_lookup
    ON element_cache(package, activity, app_version, query_type);
"""


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=5, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_DDL)
    # schema migration: add page_hash column if it doesn't exist yet
    cols = {r[1] for r in c.execute("PRAGMA table_info(element_cache)").fetchall()}
    if "page_hash" not in cols:
        c.execute("ALTER TABLE element_cache ADD COLUMN page_hash TEXT")
        c.commit()
    return c


# ── 公开 API ──────────────────────────────────────────────────────

def lookup(
    package: str,
    activity: str,
    app_version: str,
    query: str,
    query_type: str,
    confidence_threshold: int = 1,
    ttl_days: int = 7,
) -> Optional[dict]:
    """
    查找缓存坐标。返回 {center_x, center_y, bounds} 或 None。

    返回 None 的情形：
      - 没有记录
      - TTL 过期
      - hit_count < confidence_threshold（积累中，尚未可信）
    """
    now_ms = int(time.time() * 1000)
    ttl_ms = ttl_days * 86_400 * 1000

    with _conn() as c:
        row = c.execute(
            """SELECT center_x, center_y, bounds, hit_count, last_seen_ts
               FROM element_cache
               WHERE package=? AND activity=? AND app_version=?
                 AND query=? AND query_type=?
               LIMIT 1""",
            (package, activity, app_version, query, query_type),
        ).fetchone()

    if row is None:
        return None
    if now_ms - row["last_seen_ts"] > ttl_ms:
        return None  # TTL 过期
    if row["hit_count"] < confidence_threshold:
        return None  # 置信度不足，继续积累

    return {
        "center_x": row["center_x"],
        "center_y": row["center_y"],
        "bounds": row["bounds"],
    }


def upsert(
    package: str,
    activity: str,
    app_version: str,
    query: str,
    query_type: str,
    center_x: int,
    center_y: int,
    bounds: Optional[str] = None,
    source_exec: Optional[str] = None,
) -> None:
    """插入或更新缓存条目，hit_count 自动 +1，坐标使用最新值。"""
    now_ms = int(time.time() * 1000)
    with _conn() as c:
        c.execute(
            """INSERT INTO element_cache
                   (package, activity, app_version, query, query_type,
                    center_x, center_y, bounds, hit_count, last_seen_ts, source_exec)
               VALUES (?,?,?,?,?,?,?,?,1,?,?)
               ON CONFLICT(package, activity, app_version, query, query_type)
               DO UPDATE SET
                   center_x     = excluded.center_x,
                   center_y     = excluded.center_y,
                   bounds       = excluded.bounds,
                   hit_count    = hit_count + 1,
                   last_seen_ts = excluded.last_seen_ts,
                   source_exec  = excluded.source_exec""",
            (package, activity, app_version, query, query_type,
             center_x, center_y, bounds, now_ms, source_exec),
        )


# ── label + pHash 专用 API ─────────────────────────────────────────

def lookup_label(
    package: str,
    activity: str,
    app_version: str,
    label: str,
    page_hash: int,
    confidence_threshold: int = 1,
    ttl_days: int = 7,
    hamming_threshold: int = 10,
) -> Optional[dict]:
    """
    按 label + pHash 模糊匹配缓存坐标。

    查找流程：
      1. 精确匹配 (package, activity, version, label, query_type='label')
      2. 对所有候选条目计算 pHash 汉明距离，取距离最小且 <= hamming_threshold 的
      3. 校验 TTL 和置信度

    返回 {center_x, center_y, bounds, hamming_dist} 或 None。
    """
    from .phash import hamming as _hamming, from_hex as _from_hex

    now_ms = int(time.time() * 1000)
    ttl_ms = ttl_days * 86_400 * 1000

    with _conn() as c:
        rows = c.execute(
            """SELECT center_x, center_y, bounds, hit_count, last_seen_ts, page_hash
               FROM element_cache
               WHERE package=? AND activity=? AND app_version=?
                 AND query=? AND query_type='label'
                 AND page_hash IS NOT NULL""",
            (package, activity, app_version, label),
        ).fetchall()

    if not rows:
        return None

    best = None
    best_dist = hamming_threshold + 1

    for row in rows:
        # TTL 校验
        if now_ms - row["last_seen_ts"] > ttl_ms:
            continue
        # 置信度校验
        if row["hit_count"] < confidence_threshold:
            continue
        # pHash 汉明距离
        try:
            stored_hash = _from_hex(row["page_hash"])
            dist = _hamming(page_hash, stored_hash)
        except Exception:
            continue
        if dist <= hamming_threshold and dist < best_dist:
            best_dist = dist
            best = row

    if best is None:
        return None

    return {
        "center_x": best["center_x"],
        "center_y": best["center_y"],
        "bounds": best["bounds"],
        "hamming_dist": best_dist,
    }


def upsert_label(
    package: str,
    activity: str,
    app_version: str,
    label: str,
    center_x: int,
    center_y: int,
    page_hash: int,
    bounds: Optional[str] = None,
    source_exec: Optional[str] = None,
) -> None:
    """
    写入 label 类型缓存（含 page_hash）。

    注意：label 缓存的 UNIQUE key 包含 page_hash 前缀段——
    同一 label 在不同页面（pHash 差异大）各自独立存储，互不覆盖。
    但 SQLite UNIQUE 约束仍是 (package, activity, version, query, query_type)，
    同一 label 只保留最新 pHash（因为相同页面的 hash 几乎不变，不同页面已被
    lookup_label 的汉明距离过滤拦截）。
    """
    from .phash import to_hex as _to_hex

    now_ms = int(time.time() * 1000)
    hash_hex = _to_hex(page_hash)

    with _conn() as c:
        c.execute(
            """INSERT INTO element_cache
                   (package, activity, app_version, query, query_type,
                    center_x, center_y, bounds, hit_count, last_seen_ts,
                    source_exec, page_hash)
               VALUES (?,?,?,?,?,?,?,?,1,?,?,?)
               ON CONFLICT(package, activity, app_version, query, query_type)
               DO UPDATE SET
                   center_x     = excluded.center_x,
                   center_y     = excluded.center_y,
                   bounds       = excluded.bounds,
                   page_hash    = excluded.page_hash,
                   hit_count    = hit_count + 1,
                   last_seen_ts = excluded.last_seen_ts,
                   source_exec  = excluded.source_exec""",
            (package, activity, app_version, label, "label",
             center_x, center_y, bounds, now_ms, source_exec, hash_hex),
        )


def clear(package: Optional[str] = None) -> int:
    """清空缓存，返回删除行数。package=None 时清空全部。"""
    with _conn() as c:
        if package:
            cur = c.execute(
                "DELETE FROM element_cache WHERE package=?", (package,)
            )
        else:
            cur = c.execute("DELETE FROM element_cache")
        return cur.rowcount


def stats() -> dict:
    """返回缓存统计信息。"""
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM element_cache").fetchone()[0]
        by_pkg = c.execute(
            "SELECT package, COUNT(*) as cnt FROM element_cache GROUP BY package ORDER BY cnt DESC"
        ).fetchall()
        top_hits = c.execute(
            """SELECT query, package, activity, hit_count
               FROM element_cache ORDER BY hit_count DESC LIMIT 10"""
        ).fetchall()
    return {
        "total_entries": total,
        "by_package": {r["package"]: r["cnt"] for r in by_pkg},
        "top_hits": [dict(r) for r in top_hits],
        "db_path": str(_DB_PATH),
    }
