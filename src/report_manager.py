"""向后兼容层 — 外部代码可继续使用 `from report_manager import ReportManager`。"""

from report.manager import ReportManager
from report.utils import ActiveReportState, ensure_dir, now_iso, now_ts_ms, slugify

__all__ = [
    "ReportManager",
    "ActiveReportState",
    "ensure_dir",
    "now_iso",
    "now_ts_ms",
    "slugify",
]
