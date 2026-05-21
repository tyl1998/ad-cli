#!/usr/bin/env python3
"""
inspect_cache.py — 查看 ~/.ad-cli/cache/elements.db 中的缓存条目及 pHash 设置

用法：
    python3 src/scripts/inspect_cache.py                  # 查看所有条目
    python3 src/scripts/inspect_cache.py --package com.starbucks.cn
    python3 src/scripts/inspect_cache.py --type label     # 只看 pHash label 条目
    python3 src/scripts/inspect_cache.py --type text      # 只看 text/id 坐标条目
    python3 src/scripts/inspect_cache.py --config         # 只看 pHash 配置
    python3 src/scripts/inspect_cache.py --stats          # 汇总统计
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────
_DB_PATH    = Path.home() / ".ad-cli" / "cache" / "elements.db"
_CFG_PATH   = Path.home() / ".ad-cli" / "config.json"

# ── 默认配置（与 cache/config.py 保持一致）──────────────────────
_DEFAULTS = {
    "cache": {
        "confidence_threshold": 1,
        "ttl_days": 7,
        "enabled": True,
        "hamming_threshold": 10,
    }
}


# ── 工具函数 ──────────────────────────────────────────────────────

def _load_config() -> dict:
    if _CFG_PATH.exists():
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = dict(_DEFAULTS["cache"])
            cfg.update(data.get("cache", {}))
            return cfg
        except Exception:
            pass
    return dict(_DEFAULTS["cache"])


def _ts_fmt(ts_ms: int) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _ttl_status(ts_ms: int, ttl_days: int) -> str:
    now_ms = int(time.time() * 1000)
    elapsed_days = (now_ms - ts_ms) / 86_400_000
    remaining = ttl_days - elapsed_days
    if remaining <= 0:
        return f"❌ 已过期 ({elapsed_days:.1f}d)"
    elif remaining < 1:
        return f"⚠️  即将过期 ({remaining*24:.1f}h)"
    else:
        return f"✅ 有效 (剩余 {remaining:.1f}d)"


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _from_hex(h: str) -> int:
    return int(h, 16)


def _conn() -> sqlite3.Connection:
    if not _DB_PATH.exists():
        print(f"❌ 数据库不存在: {_DB_PATH}")
        sys.exit(1)
    c = sqlite3.connect(str(_DB_PATH), timeout=5)
    c.row_factory = sqlite3.Row
    return c


# ── 显示函数 ──────────────────────────────────────────────────────

def show_config(cfg: dict) -> None:
    print("=" * 60)
    print("📋  pHash / 缓存 配置")
    print("=" * 60)
    print(f"  配置文件       : {_CFG_PATH}")
    print(f"  缓存开关       : {'✅ 开启' if cfg['enabled'] else '❌ 关闭'}")
    print(f"  置信度阈值     : {cfg['confidence_threshold']}  (hit_count >= 此值才信任)")
    print(f"  TTL            : {cfg['ttl_days']} 天")
    print(f"  pHash 汉明阈值 : {cfg['hamming_threshold']}  (0=完全相同, 64=完全不同)")
    print()


def show_stats(cfg: dict) -> None:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM element_cache").fetchone()[0]
        by_pkg = c.execute(
            "SELECT package, COUNT(*) as cnt, SUM(hit_count) as hits "
            "FROM element_cache GROUP BY package ORDER BY cnt DESC"
        ).fetchall()
        by_type = c.execute(
            "SELECT query_type, COUNT(*) as cnt FROM element_cache GROUP BY query_type"
        ).fetchall()
        expired = c.execute(
            "SELECT COUNT(*) FROM element_cache WHERE last_seen_ts < ?",
            (int(time.time() * 1000) - cfg["ttl_days"] * 86_400_000,)
        ).fetchone()[0]

    print("=" * 60)
    print("📊  缓存统计")
    print("=" * 60)
    print(f"  总条目数  : {total}")
    print(f"  已过期    : {expired} 条")
    print(f"  数据库    : {_DB_PATH}  ({_DB_PATH.stat().st_size // 1024} KB)")
    print()
    print("  按 package 分布：")
    for r in by_pkg:
        print(f"    {r['package']:<45} {r['cnt']:>4} 条  累计命中 {r['hits']} 次")
    print()
    print("  按类型分布：")
    for r in by_type:
        print(f"    {r['query_type']:<20} {r['cnt']:>4} 条")
    print()


def show_entries(rows, cfg: dict, show_phash: bool = True) -> None:
    if not rows:
        print("  (无匹配条目)")
        return

    for r in rows:
        is_label = r["query_type"] == "label"
        ttl_s    = _ttl_status(r["last_seen_ts"], cfg["ttl_days"])
        trust_s  = "✅ 可信" if r["hit_count"] >= cfg["confidence_threshold"] else f"⏳ 积累中({r['hit_count']}/{cfg['confidence_threshold']})"

        print(f"  ─── #{r['id']}  [{r['query_type']}]  {r['query']!r}")
        print(f"      package   : {r['package']}")
        print(f"      activity  : {r['activity']}")
        print(f"      version   : {r['app_version'] or '(任意)'}")
        print(f"      坐标      : ({r['center_x']}, {r['center_y']})  bounds={r['bounds']}")
        print(f"      命中次数  : {r['hit_count']}  → {trust_s}")
        print(f"      最后更新  : {_ts_fmt(r['last_seen_ts'])}  → {ttl_s}")

        if is_label and show_phash:
            ph = r["page_hash"]
            if ph:
                ph_int = _from_hex(ph)
                print(f"      pHash     : {ph}  (int={ph_int})")
            else:
                print(f"      pHash     : ⚠️  未记录")

        if r["source_exec"]:
            print(f"      来源      : {r['source_exec']}")
        print()


# ── 主程序 ────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="查看 ad-cli 元素坐标缓存及 pHash 设置")
    ap.add_argument("--package", "-p", metavar="PKG",   help="只看指定 package")
    ap.add_argument("--type",    "-t", metavar="TYPE",  help="只看指定类型: label / text / id / ...")
    ap.add_argument("--config",  "-c", action="store_true", help="只显示配置信息")
    ap.add_argument("--stats",   "-s", action="store_true", help="显示汇总统计")
    ap.add_argument("--expired",        action="store_true", help="只显示已过期条目")
    ap.add_argument("--limit",   "-n", type=int, default=50, help="最多显示条数 (默认50)")
    args = ap.parse_args()

    cfg = _load_config()

    # 总是显示配置
    show_config(cfg)

    if args.config:
        return

    if args.stats or (not args.package and not args.type and not args.expired):
        show_stats(cfg)

    if args.config or (args.stats and not args.package and not args.type):
        return

    # ── 查询条目 ─────────────────────────────────────────────────
    where, params = [], []

    if args.package:
        where.append("package = ?")
        params.append(args.package)

    if args.type:
        where.append("query_type = ?")
        params.append(args.type)

    if args.expired:
        ttl_ms = int(time.time() * 1000) - cfg["ttl_days"] * 86_400_000
        where.append("last_seen_ts < ?")
        params.append(ttl_ms)

    sql = "SELECT * FROM element_cache"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_seen_ts DESC LIMIT ?"
    params.append(args.limit)

    with _conn() as c:
        rows = c.execute(sql, params).fetchall()

    label = []
    if args.package:
        label.append(f"package={args.package}")
    if args.type:
        label.append(f"type={args.type}")
    if args.expired:
        label.append("已过期")

    title = "  ".join(label) if label else "全部"
    print("=" * 60)
    print(f"🗃️   缓存条目  ({title})  — 共 {len(rows)} 条")
    print("=" * 60)
    show_entries(rows, cfg)


if __name__ == "__main__":
    main()
