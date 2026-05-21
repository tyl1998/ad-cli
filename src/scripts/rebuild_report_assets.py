#!/usr/bin/env python3
import json
import os
import shutil
import sys

from report_manager import ReportManager


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python rebuild_report_assets.py <report_dir>")
        return 1

    report_dir = os.path.abspath(sys.argv[1])
    report_json = os.path.join(report_dir, "report.json")
    if not os.path.exists(report_json):
        print(f"report.json not found: {report_json}")
        return 1

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    working_dir = data.get("meta", {}).get("working_dir") or os.path.dirname(report_dir)
    manager = ReportManager(working_dir)

    for execution in data.get("executions", []):
        result = execution.get("result") or {}
        source = result.get("screenshot")
        target_rel = execution.get("screenshot")
        if not source or not target_rel or not os.path.exists(source):
            continue

        target_abs = os.path.join(report_dir, target_rel.replace("./", "", 1))
        os.makedirs(os.path.dirname(target_abs), exist_ok=True)
        shutil.copy2(source, target_abs)

        spotlight = execution.get("spotlight")
        execution["focus_preview"] = None
        if spotlight:
            execution["focus_preview"] = manager._build_focus_preview(
                report_dir,
                execution.get("id") or os.path.splitext(os.path.basename(target_abs))[0],
                target_abs,
                spotlight,
            )

    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    manager._render_html(report_dir, data)
    print(f"rebuilt: {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
