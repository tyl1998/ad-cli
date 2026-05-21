"""
报告工具函数与共享数据结构
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime


ACTIVE_REPORT_STATE_FILE = ".ad_cli_active_report.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def now_ts_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


def slugify(value: str) -> str:
    safe = []
    for ch in value.strip().lower():
        if ch.isalnum():
            safe.append(ch)
        elif ch in (" ", "-", "_"):
            safe.append("-")
    slug = "".join(safe).strip("-")
    return slug or "report"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


@dataclass
class ActiveReportState:
    report_dir: str
    suite_name: str
    run_id: str
