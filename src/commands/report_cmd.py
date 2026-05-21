"""报告子命令实现 + 执行记录钩子

包含：
  - get_report_manager / _resolve_report_dir / _candidate_report_roots / _port_is_open
  - cmd_report_start/status/case_start/case_end/finalize/note/serve
  - maybe_record_execution（每条命令执行后写 execution JSON）
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

from adb_client import ADBClient
from output import ok, error
from report_manager import ReportManager
from commands.perception import _take_screenshot


# ── 工具函数 ──────────────────────────────────────────────────────

def get_report_manager() -> ReportManager:
    """以项目根目录（ad-cli/）作为 working_dir，确保报告写入 <project>/report/。"""
    # __file__ = src/commands/report_cmd.py
    # commands_dir = src/commands/
    # src_dir      = src/
    # project_root = ad-cli/
    commands_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(commands_dir)
    project_root = os.path.dirname(src_dir)
    return ReportManager(project_root)


def _candidate_report_roots() -> list[str]:
    # 优先用 __file__ 推导的项目根，再兜底 cwd
    commands_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(commands_dir)
    project_root = os.path.dirname(src_dir)
    cwd = os.getcwd()
    candidates = [
        os.path.join(project_root, "report"),   # ad-cli/report/  ← 正确位置
        os.path.join(cwd, "report"),             # cwd/report/     ← 兜底
        os.path.join(os.path.dirname(cwd), "report"),  # parent/report/
    ]
    unique: list[str] = []
    for root in candidates:
        normalized = os.path.abspath(root)
        if normalized not in unique:
            unique.append(normalized)
    return unique


def _resolve_report_dir(name: str | None = None) -> str:
    manager = get_report_manager()
    if name:
        candidates = [
            name,
            os.path.join(os.getcwd(), name),
            os.path.join(os.path.dirname(os.getcwd()), name),
        ]
        for root in _candidate_report_roots():
            candidates.append(os.path.join(root, name))
        for c in candidates:
            c_abs = os.path.abspath(c)
            if os.path.isdir(c_abs) and os.path.exists(os.path.join(c_abs, "index.html")):
                return c_abs
        raise RuntimeError(f"找不到报告目录：{name}")

    active = manager.load_active_state()
    if active and os.path.isdir(active.report_dir):
        return active.report_dir

    latest_dir = None
    latest_mtime = -1.0
    for root in _candidate_report_roots():
        if not os.path.isdir(root):
            continue
        for child in os.listdir(root):
            candidate = os.path.join(root, child)
            if not os.path.isdir(candidate):
                continue
            if not os.path.exists(os.path.join(candidate, "index.html")):
                continue
            mtime = os.path.getmtime(candidate)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_dir = candidate

    if latest_dir:
        return os.path.abspath(latest_dir)
    raise RuntimeError("未找到可预览的报告，请先执行 report start / finalize 生成报告")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ── 报告命令实现 ──────────────────────────────────────────────────

def cmd_report_start(adb: ADBClient | None, suite_name: str,
                     output_dir: str | None = None) -> dict:
    manager = get_report_manager()
    device_info = {}
    if adb and adb.is_connected():
        try:
            device_info = adb.get_device_info()
        except Exception:
            pass
    report = manager.start_report(suite_name=suite_name,
                                   output_dir=output_dir,
                                   device_info=device_info)
    return ok("report start", data={
        "suite_name": report["meta"]["suite_name"],
        "run_id":     report["meta"]["run_id"],
        "report_dir": report["meta"]["report_dir"],
        "html":       os.path.join(report["meta"]["report_dir"], "index.html"),
        "json":       os.path.join(report["meta"]["report_dir"], "report.json"),
    })


def cmd_report_status() -> dict:
    manager = get_report_manager()
    status = manager.get_status()
    if not status:
        return error("report status", "REPORT_NOT_ACTIVE", "当前没有激活中的报告")
    return ok("report status", data=status)


def cmd_report_case_start(case_name: str, description: str | None = None) -> dict:
    case = get_report_manager().start_case(case_name, description)
    return ok("report case-start", data=case)


def cmd_report_case_end(status: str = "passed", summary: str | None = None) -> dict:
    case = get_report_manager().end_case(status=status, summary=summary)
    return ok("report case-end", data=case)


def cmd_report_finalize(force: bool = False) -> dict:
    result = get_report_manager().finalize(force=force)
    return ok("report finalize", data=result)


def cmd_report_note(title: str, content: str | None = None,
                    level: str = "info",
                    screenshot_source: str | None = None) -> dict:
    execution = get_report_manager().add_note(
        title=title, content=content,
        level=level, screenshot_source=screenshot_source,
    )
    return ok("report note", data=execution)


def _pid_file() -> str:
    return os.path.join(os.path.expanduser("~"), ".ad-cli", "report_server.pid")


def cmd_report_serve(name: str | None = None, port: int = 8765) -> dict:
    report_dir = _resolve_report_dir(name)
    root_dir = os.path.dirname(report_dir)
    run_dir_name = os.path.basename(report_dir)
    url = f"http://127.0.0.1:{port}/{run_dir_name}/index.html"
    root_url = f"http://127.0.0.1:{port}/"

    get_report_manager().rebuild_root_index(root_dir)

    if not _port_is_open(port):
        # 优先使用项目 .venv 中的 python，fallback 到当前解释器
        _commands_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(os.path.dirname(_commands_dir))
        _venv_py = os.path.join(_project_root, ".venv", "bin", "python3")
        _python_exe = _venv_py if os.path.isfile(_venv_py) else sys.executable
        with open(os.devnull, "wb") as devnull:
            process = subprocess.Popen(
                [_python_exe, "-m", "http.server", str(port)],
                cwd=root_dir, stdout=devnull, stderr=devnull,
                start_new_session=True,
            )
        time.sleep(0.5)
        if process.poll() is not None or not _port_is_open(port):
            raise RuntimeError(f"报告服务启动失败，请检查端口 {port} 是否可用")
        pid, reused = process.pid, False
        # 写入 PID 文件
        os.makedirs(os.path.dirname(_pid_file()), exist_ok=True)
        with open(_pid_file(), "w") as f:
            f.write(f"{pid}:{port}")
    else:
        pid, reused = None, True

    return ok("report serve", data={
        "report_dir": report_dir,
        "root_dir":   root_dir,
        "port": port,
        "url":  url,
        "root_url": root_url,
        "pid":  pid,
        "reused_existing_server": reused,
    })


def cmd_report_serve_stop() -> dict:
    """停止后台 report HTTP server（通过 PID 文件）。"""
    import signal
    pf = _pid_file()
    if not os.path.exists(pf):
        return error("report stop", "NOT_RUNNING", "未找到运行中的 report server（无 PID 文件）")
    with open(pf) as f:
        content = f.read().strip()
    try:
        pid_str, port_str = content.split(":")
        pid, port = int(pid_str), int(port_str)
    except Exception:
        os.remove(pf)
        return error("report stop", "BAD_PID_FILE", f"PID 文件格式错误: {content}")
    try:
        os.kill(pid, signal.SIGTERM)
        os.remove(pf)
        return ok("report stop", data={"pid": pid, "port": port, "message": f"已停止 report server (pid={pid}, port={port})"})
    except ProcessLookupError:
        os.remove(pf)
        return ok("report stop", data={"pid": pid, "port": port, "message": f"进程 {pid} 已不存在，清理 PID 文件"})
    except Exception as e:
        return error("report stop", "KILL_FAILED", str(e))


# ── 执行记录钩子 ──────────────────────────────────────────────────

def maybe_record_execution(args, result: dict, started_at: float,
                            ended_at: float,
                            adb: ADBClient | None = None) -> None:
    if args.group == "report":
        return

    manager = get_report_manager()
    if not manager.has_active_report():
        return

    page_info = None
    if adb:
        try:
            page_info = adb.get_current_page()
        except Exception:
            pass

    screenshot_source = None
    if isinstance(result, dict):
        screenshot_source = result.get("screenshot")
        if not screenshot_source and isinstance(result.get("data"), dict):
            screenshot_source = result["data"].get("path")

    dump_summary = None
    if args.group == "dump" and isinstance(result, dict):
        dump_summary = {
            "mode":           result.get("mode"),
            "returned":       result.get("returned"),
            "total_elements": result.get("total_elements"),
            "reason":         result.get("reason"),
        }

    manager.record_execution(
        command_name=args.group,
        argv=sys.argv[1:],
        result=result,
        started_at_ts=started_at,
        ended_at_ts=ended_at,
        page_info=page_info,
        screenshot_source=screenshot_source,
        dump_summary=dump_summary,
    )
