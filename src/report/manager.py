"""ReportManager 主类 — 报告生命周期管理、IO 操作及执行记录。"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from output import ErrorCode, ReportError
from report.analysis import (
    build_execution_analysis,
    build_report_summary,
    derive_business_steps,
)
from report.assets import build_focus_preview, persist_visual_assets
from report.html_renderer import build_html, build_root_index_html
from report.utils import (
    ACTIVE_REPORT_STATE_FILE,
    ActiveReportState,
    ensure_dir,
    now_iso,
    now_ts_ms,
    slugify,
)


class ReportManager:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.state_file = os.path.join(working_dir, ACTIVE_REPORT_STATE_FILE)

    # ── active state ─────────────────────────────────────────

    def has_active_report(self) -> bool:
        return os.path.exists(self.state_file)

    def load_active_state(self) -> ActiveReportState | None:
        if not self.has_active_report():
            return None
        with open(self.state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ActiveReportState(
            report_dir=data["report_dir"],
            suite_name=data["suite_name"],
            run_id=data["run_id"],
        )

    def save_active_state(self, report_dir: str, suite_name: str, run_id: str) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "report_dir": report_dir,
                    "suite_name": suite_name,
                    "run_id": run_id,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def clear_active_state(self) -> None:
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    # ── report data io ───────────────────────────────────────

    def _report_json_path(self, report_dir: str) -> str:
        return os.path.join(report_dir, "report.json")

    def _index_html_path(self, report_dir: str) -> str:
        return os.path.join(report_dir, "index.html")

    def _executions_dir(self, report_dir: str) -> str:
        return os.path.join(report_dir, "executions")

    def _screenshots_dir(self, report_dir: str) -> str:
        return os.path.join(report_dir, "screenshots")

    def _load_report_data(self, report_dir: str) -> dict:
        report_json = self._report_json_path(report_dir)
        with open(report_json, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_report_data(self, report_dir: str, data: dict) -> None:
        data = self._prepare_report_data(data)
        with open(self._report_json_path(report_dir), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _prepare_report_data(self, data: dict) -> dict:
        executions = data.get("executions", [])
        cases = data.get("cases", [])

        for execution in executions:
            execution["analysis"] = build_execution_analysis(execution)

        for case in cases:
            case_executions = [item for item in executions if item.get("case_id") == case.get("id")]
            case["business_steps"] = derive_business_steps(case_executions)
            checkpoint_ids = [
                item["id"]
                for item in case_executions
                if item.get("analysis", {}).get("evidence_level") == "checkpoint"
            ]
            support_ids = [
                item["id"]
                for item in case_executions
                if item.get("analysis", {}).get("evidence_level") == "supporting"
            ]
            fallback_count = sum(
                1 for item in case_executions if item.get("analysis", {}).get("is_fallback")
            )
            issue_count = sum(
                1 for item in case_executions if item.get("analysis", {}).get("issue_flags")
            )
            case["evidence_execution_ids"] = checkpoint_ids
            case["supporting_screenshot_ids"] = support_ids
            case["summary_card"] = {
                "case_name": case.get("name"),
                "status": case.get("status"),
                "conclusion": case.get("summary") or case.get("description") or "",
                "business_step_count": len(case.get("business_steps", [])),
                "execution_count": len(case_executions),
                "evidence_count": len(checkpoint_ids),
                "supporting_screenshot_count": len(support_ids),
                "fallback_count": fallback_count,
                "issue_count": issue_count,
                "key_path": [step.get("title") for step in case.get("business_steps", [])[:6]],
            }

        data.setdefault("meta", {})["summary"] = build_report_summary(data)
        return data

    # ── html rendering ────────────────────────────────────────

    def _render_html(self, report_dir: str, data: dict) -> None:
        html = build_html(data)
        with open(self._index_html_path(report_dir), "w", encoding="utf-8") as f:
            f.write(html)

    # ── lifecycle ─────────────────────────────────────────────

    def start_report(
        self,
        suite_name: str,
        output_dir: str | None = None,
        device_info: dict | None = None,
    ) -> dict:
        if self.has_active_report():
            active = self.load_active_state()
            raise ReportError(
                ErrorCode.REPORT_NOT_ACTIVE,
                f"已有激活中的报告：{active.report_dir if active else self.state_file}，请先 finalize"
            )

        run_id = f"{slugify(suite_name)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        report_dir = os.path.abspath(output_dir) if output_dir else os.path.abspath(
            os.path.join(self.working_dir, "report", run_id)
        )

        if os.path.exists(report_dir) and os.listdir(report_dir):
            raise ReportError(ErrorCode.RUNTIME_ERROR, f"报告目录已存在且不为空：{report_dir}")

        ensure_dir(report_dir)
        ensure_dir(self._executions_dir(report_dir))
        ensure_dir(self._screenshots_dir(report_dir))

        report_data = {
            "meta": {
                "run_id": run_id,
                "suite_name": suite_name,
                "status": "running",
                "started_at": now_iso(),
                "finished_at": None,
                "working_dir": self.working_dir,
                "report_dir": report_dir,
                "device": device_info or {},
            },
            "current_case_id": None,
            "case_seq": 0,
            "execution_seq": 0,
            "cases": [],
            "executions": [],
        }
        self._save_report_data(report_dir, report_data)
        self._render_html(report_dir, report_data)
        self.save_active_state(report_dir, suite_name, run_id)
        self.rebuild_root_index(os.path.dirname(report_dir))
        return report_data

    def get_status(self) -> dict | None:
        active = self.load_active_state()
        if not active:
            return None
        data = self._load_report_data(active.report_dir)
        return {
            "report_dir": active.report_dir,
            "suite_name": active.suite_name,
            "run_id": active.run_id,
            "meta": data.get("meta", {}),
            "current_case_id": data.get("current_case_id"),
            "case_count": len(data.get("cases", [])),
            "execution_count": len(data.get("executions", [])),
        }

    def start_case(self, case_name: str, description: str | None = None) -> dict:
        active = self.load_active_state()
        if not active:
            raise ReportError(ErrorCode.REPORT_NOT_ACTIVE, "当前没有激活中的报告，请先执行 report start")

        data = self._load_report_data(active.report_dir)
        current_case_id = data.get("current_case_id")
        if current_case_id:
            for case in data["cases"]:
                if case["id"] == current_case_id and case.get("status") == "running":
                    case["status"] = "unfinished"
                    case["finished_at"] = now_iso()
                    case["summary"] = "开启新 case 时自动结束上一个未关闭 case"
        data["case_seq"] += 1
        case_id = f"case-{data['case_seq']:03d}"
        case = {
            "id": case_id,
            "name": case_name,
            "description": description,
            "status": "running",
            "started_at": now_iso(),
            "finished_at": None,
            "execution_ids": [],
        }
        data["cases"].append(case)
        data["current_case_id"] = case_id
        self._save_report_data(active.report_dir, data)
        self._render_html(active.report_dir, data)
        return case

    def add_note(
        self,
        title: str,
        content: str | None = None,
        level: str = "info",
        screenshot_source: str | None = None,
    ) -> dict:
        active = self.load_active_state()
        if not active:
            raise ReportError(ErrorCode.REPORT_NOT_ACTIVE, "当前没有激活中的报告，请先执行 report start")

        data = self._load_report_data(active.report_dir)
        data["execution_seq"] += 1
        execution_id = f"exec-{data['execution_seq']:04d}"
        current_case_id = data.get("current_case_id")
        visuals = persist_visual_assets(
            active.report_dir,
            execution_id,
            screenshot_source,
            spotlight=None,
        )

        execution = {
            "id": execution_id,
            "case_id": current_case_id,
            "logTime": now_ts_ms(),
            "name": "report-note",
            "argv": [title],
            "status": level,
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "duration_ms": 0,
            "page": {},
            "screenshot": visuals.get("screenshot"),
            "focus_preview": visuals.get("focus_preview"),
            "dump_summary": {},
            "result": {
                "status": "ok",
                "command": "report note",
                "data": {
                    "title": title,
                    "content": content,
                    "level": level,
                },
            },
            "note": {
                "title": title,
                "content": content,
                "level": level,
            },
        }

        data["executions"].append(execution)
        if current_case_id:
            for case in data["cases"]:
                if case["id"] == current_case_id:
                    case.setdefault("execution_ids", []).append(execution_id)
                    break

        self._save_execution_file(active.report_dir, execution)
        self._save_report_data(active.report_dir, data)
        self._render_html(active.report_dir, data)
        return execution

    def end_case(self, status: str = "passed", summary: str | None = None) -> dict:
        active = self.load_active_state()
        if not active:
            raise ReportError(ErrorCode.REPORT_NOT_ACTIVE, "当前没有激活中的报告，请先执行 report start")

        data = self._load_report_data(active.report_dir)
        current_case_id = data.get("current_case_id")
        if not current_case_id:
            raise ReportError(ErrorCode.REPORT_CASE_NOT_ACTIVE, "当前没有运行中的 case，请先执行 report case-start")

        target = None
        for case in data["cases"]:
            if case["id"] == current_case_id:
                target = case
                break
        if not target:
            raise ReportError(ErrorCode.REPORT_CASE_NOT_ACTIVE, f"找不到当前 case：{current_case_id}")

        target["status"] = status
        target["finished_at"] = now_iso()
        if summary:
            target["summary"] = summary
        data["current_case_id"] = None
        self._save_report_data(active.report_dir, data)
        self._render_html(active.report_dir, data)
        return target

    def finalize(self, force: bool = False) -> dict:
        active = self.load_active_state()
        if not active:
            raise ReportError(ErrorCode.REPORT_NOT_ACTIVE, "当前没有激活中的报告")

        data = self._load_report_data(active.report_dir)
        current_case_id = data.get("current_case_id")
        if current_case_id:
            if not force:
                raise ReportError(ErrorCode.REPORT_FINALIZE_BLOCKED, "当前仍有运行中的 case，请先执行 report case-end，或使用 report finalize --force")
            for case in data["cases"]:
                if case["id"] == current_case_id and case["status"] == "running":
                    case["status"] = "unfinished"
                    case["finished_at"] = now_iso()
                    case["summary"] = case.get("summary") or "通过 finalize --force 自动收口"
            data["current_case_id"] = None

        data["meta"]["status"] = "finished"
        data["meta"]["finished_at"] = now_iso()
        self._save_report_data(active.report_dir, data)
        self._render_html(active.report_dir, data)
        self.clear_active_state()
        self.rebuild_root_index(os.path.dirname(active.report_dir))
        return {
            "report_dir": active.report_dir,
            "html": self._index_html_path(active.report_dir),
            "json": self._report_json_path(active.report_dir),
            "forced": force,
        }

    # ── execution recording ──────────────────────────────────

    def record_execution(
        self,
        command_name: str,
        argv: list[str],
        result: dict,
        started_at_ts: float,
        ended_at_ts: float,
        page_info: dict | None = None,
        screenshot_source: str | None = None,
        dump_summary: dict | None = None,
    ) -> dict | None:
        active = self.load_active_state()
        if not active:
            return None

        data = self._load_report_data(active.report_dir)
        data["execution_seq"] += 1
        execution_id = f"exec-{data['execution_seq']:04d}"
        current_case_id = data.get("current_case_id")

        spotlight = result.get("spotlight") if isinstance(result, dict) else None
        visuals = persist_visual_assets(
            active.report_dir,
            execution_id,
            screenshot_source,
            spotlight=spotlight,
        )

        execution = {
            "id": execution_id,
            "case_id": current_case_id,
            "logTime": int(started_at_ts * 1000),
            "name": command_name,
            "argv": argv,
            "status": result.get("status", "unknown"),
            "started_at": datetime.fromtimestamp(started_at_ts).isoformat(timespec="seconds"),
            "finished_at": datetime.fromtimestamp(ended_at_ts).isoformat(timespec="seconds"),
            "duration_ms": int((ended_at_ts - started_at_ts) * 1000),
            "page": page_info or {},
            "screenshot": visuals.get("screenshot"),
            "focus_preview": visuals.get("focus_preview"),
            "spotlight": spotlight,
            "dump_summary": dump_summary or {},
            "result": result,
        }

        data["executions"].append(execution)
        if current_case_id:
            for case in data["cases"]:
                if case["id"] == current_case_id:
                    case.setdefault("execution_ids", []).append(execution_id)
                    break

        self._save_execution_file(active.report_dir, execution)
        self._save_report_data(active.report_dir, data)
        self._render_html(active.report_dir, data)
        return execution

    def _save_execution_file(self, report_dir: str, execution: dict) -> None:
        file_name = f"{execution['id']}.execution.json"
        file_path = os.path.join(self._executions_dir(report_dir), file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(execution, f, ensure_ascii=False, indent=2)

    def _persist_visual_assets(
        self,
        report_dir: str,
        execution_id: str,
        screenshot_source: str | None,
        spotlight: dict | None = None,
    ) -> dict[str, str | None]:
        return persist_visual_assets(report_dir, execution_id, screenshot_source, spotlight)

    def _build_focus_preview(
        self,
        report_dir: str,
        execution_id: str,
        image_path: str,
        spotlight: dict,
    ) -> str | None:
        return build_focus_preview(report_dir, execution_id, image_path, spotlight)

    # ── root index ───────────────────────────────────────────

    def rebuild_root_index(self, report_root: str) -> None:
        """扫描 report_root，生成列出所有 run 的 index.html（风格与子报告一致）。"""
        if not os.path.isdir(report_root):
            return
        runs = []
        for child in sorted(os.listdir(report_root), reverse=True):
            child_path = os.path.join(report_root, child)
            if not os.path.isdir(child_path):
                continue
            json_path = os.path.join(child_path, "report.json")
            if not os.path.exists(json_path):
                continue
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("meta", {})
                cases = data.get("cases", [])
                runs.append({
                    "run_id": meta.get("run_id", child),
                    "suite_name": meta.get("suite_name", child),
                    "status": meta.get("status", "unknown"),
                    "started_at": meta.get("started_at", ""),
                    "finished_at": meta.get("finished_at", ""),
                    "total_cases": len(cases),
                    "passed": len([c for c in cases if c.get("status") == "passed"]),
                    "failed": len([c for c in cases if c.get("status") == "failed"]),
                    "skipped": len([c for c in cases if c.get("status") == "skipped"]),
                    "report_dir": child_path,
                    "run_dir_name": child,
                })
            except Exception:
                continue
        html = build_root_index_html(runs)
        index_path = os.path.join(report_root, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)

    # ── rebuild helper (for rebuild_report_assets.py) ────────

    def rebuild_report_assets(self, report_dir: str) -> dict:
        """重建指定报告目录的截图资产与 HTML（供 rebuild_report_assets.py 调用）。"""
        data = self._load_report_data(report_dir)
        self._save_report_data(report_dir, data)
        self._render_html(report_dir, data)
        return {"report_dir": report_dir, "html": self._index_html_path(report_dir)}
