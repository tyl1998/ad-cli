"""
回放模块 — 支持两种来源：
  1. replay_report()    — 回放 report executions（报告中记录的命令步骤）
  2. replay_recording() — 回放 mirror 录制脚本（原始坐标操作）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# 业务步骤命令集合（用于非 full 模式过滤）
_BUSINESS_COMMANDS = {"tap", "input", "scroll", "back", "keyevent"}


# ══════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════

def _load_executions(report_dir: str) -> list[dict]:
    """加载 executions/ 目录下所有 execution JSON，按文件名排序"""
    exec_dir = os.path.join(report_dir, "executions")
    if not os.path.isdir(exec_dir):
        return []
    files = sorted(f for f in os.listdir(exec_dir) if f.endswith(".execution.json"))
    result = []
    for fname in files:
        try:
            with open(os.path.join(exec_dir, fname), "r", encoding="utf-8") as fp:
                result.append(json.load(fp))
        except Exception:
            continue
    return result


# ══════════════════════════════════════════════════════════════════
# 1. 报告步骤回放
# ══════════════════════════════════════════════════════════════════

def replay_report(
    report_dir: str,
    full: bool = False,
    case_id: Optional[str] = None,
    generate_report: bool = False,
    speed_factor: float = 1.0,
    dry_run: bool = False,
) -> dict:
    """
    回放报告中记录的命令步骤。

    Args:
        report_dir:       报告目录路径
        full:             True = 全量（含 dump/wait），False = 仅业务步骤
        case_id:          只回放指定 case（case_id 或 case_name）
        generate_report:  回放时是否生成新报告（当前版本暂不实现，预留）
        speed_factor:     时间倍率（1.0=原速，0.5=慢放，2.0=快放）
        dry_run:          只打印命令，不实际执行
    """
    executions = _load_executions(report_dir)
    if not executions:
        return {
            "status": "error", "code": "NO_EXECUTIONS",
            "message": f"找不到执行记录: {report_dir}",
        }

    # 按 case 过滤
    if case_id:
        executions = [
            e for e in executions
            if e.get("case_id") == case_id or e.get("case_name") == case_id
        ]

    # 业务步骤过滤（非 full 模式）
    if not full:
        executions = [
            e for e in executions
            if e.get("command_name") in _BUSINESS_COMMANDS
        ]

    if not executions:
        return {
            "status": "error", "code": "NO_STEPS",
            "message": "没有可回放的步骤" + ("（业务步骤为空，可用 --full 全量回放）" if not full else ""),
        }

    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    results: list[dict] = []
    prev_ended_ts: Optional[float] = None

    for i, exc in enumerate(executions):
        argv: list[str] = exc.get("argv", [])
        started_ts: float = exc.get("started_at_ts", 0)
        ended_ts: float = exc.get("ended_at_ts", 0)
        duration_ms: float = (ended_ts - started_ts) if ended_ts > started_ts else 0

        # 步骤间延迟：还原原始执行节奏
        if i > 0 and prev_ended_ts and started_ts:
            gap_ms = max(0.0, started_ts - prev_ended_ts)
            delay_s = (gap_ms / 1000.0) / max(speed_factor, 0.01)
            if not dry_run and delay_s > 0:
                time.sleep(min(delay_s, 30.0))

        prev_ended_ts = ended_ts

        if dry_run:
            results.append({
                "seq": i + 1,
                "command": exc.get("command_name"),
                "argv": argv,
                "original_duration_ms": duration_ms,
                "status": "dry-run",
            })
            continue

        cmd = [sys.executable, main_py] + argv
        try:
            t0 = time.time()
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            actual_ms = int((time.time() - t0) * 1000)
            try:
                out = json.loads(proc.stdout)
            except Exception:
                out = {"raw": proc.stdout[:300]}
            results.append({
                "seq": i + 1,
                "command": exc.get("command_name"),
                "argv": argv,
                "status": out.get("status", "?"),
                "actual_ms": actual_ms,
            })
        except subprocess.TimeoutExpired:
            results.append({"seq": i + 1, "argv": argv, "status": "timeout"})
        except Exception as e:
            results.append({"seq": i + 1, "argv": argv, "status": "error", "error": str(e)})

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "error": sum(1 for r in results if r.get("status") in ("error", "timeout")),
        "dry_run": dry_run,
    }

    return {
        "status": "ok",
        "command": "replay",
        "report_dir": report_dir,
        "mode": "full" if full else "business",
        "summary": summary,
        "steps": results,
    }


# ══════════════════════════════════════════════════════════════════
# 2. 录制脚本回放
# ══════════════════════════════════════════════════════════════════

def replay_recording(
    name: str,
    speed_factor: float = 1.0,
    dry_run: bool = False,
) -> dict:
    """
    回放 mirror 录制脚本（~/.ad-cli/recordings/*.replay.json）。

    Args:
        name:         录制名称（文件名前缀）或完整路径
        speed_factor: 时间倍率
        dry_run:      只打印，不执行
    """
    recordings_dir = Path.home() / ".ad-cli" / "recordings"

    # 定位录制文件
    path: Optional[Path] = None
    candidate = Path(name)
    if candidate.exists():
        path = candidate
    else:
        matches = sorted(recordings_dir.glob(f"{name}*.replay.json"), reverse=True)
        if not matches:
            matches = sorted(
                [f for f in recordings_dir.glob("*.replay.json") if name in f.stem],
                reverse=True,
            )
        if matches:
            path = matches[0]

    if path is None:
        return {
            "status": "error", "code": "NOT_FOUND",
            "message": f"找不到录制文件: {name}（搜索目录: {recordings_dir}）",
        }

    with open(path, "r", encoding="utf-8") as f:
        recording = json.load(f)

    steps: list[dict] = recording.get("steps", [])
    if not steps:
        return {"status": "error", "code": "EMPTY", "message": "录制文件中没有步骤"}

    meta = recording.get("meta", {})
    serial: Optional[str] = meta.get("device") or None

    if dry_run:
        return {
            "status": "ok",
            "command": "replay",
            "recording": str(path),
            "meta": meta,
            "steps": [{"seq": s.get("seq", i + 1), "type": s.get("type"), "status": "dry-run", **{
                k: v for k, v in s.items() if k not in ("seq", "type", "delay_before_ms")
            }} for i, s in enumerate(steps)],
            "summary": {"total": len(steps), "dry_run": True},
        }

    # 使用 ADBClient 直接操作（录制是帧坐标，回放前需缩放到屏幕坐标）
    try:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from adb_client import ADBClient
        adb = ADBClient(serial) if serial else ADBClient()
        if not adb.is_connected():
            return {"status": "error", "code": "DEVICE_DISCONNECTED", "message": "设备未连接"}
    except Exception as e:
        return {"status": "error", "code": "ADB_ERROR", "message": str(e)}

    # 回放前：提示用户确认起始状态（不自动跳转，因为录制状态无法可靠还原）
    start_page = meta.get("start_page", {})

    # 计算帧坐标 → 屏幕坐标的缩放比例
    frame_w, frame_h = meta.get("resolution", [0, 0])
    scale_x, scale_y = 1.0, 1.0
    if frame_w > 0 and frame_h > 0:
        try:
            screen_size = adb.run("shell", "wm", "size")
            # 解析 "Override size: 1080x2400" 或 "Physical size: 1260x2800"
            import re as _re
            m = _re.search(r"Override size:\s*(\d+)x(\d+)", screen_size)
            if not m:
                m = _re.search(r"Physical size:\s*(\d+)x(\d+)", screen_size)
            if m:
                sw, sh = int(m.group(1)), int(m.group(2))
                scale_x = sw / frame_w
                scale_y = sh / frame_h
        except Exception:
            pass  # 无法获取屏幕尺寸则不缩放

    def _scale_tap(x: int, y: int):
        return int(x * scale_x), int(y * scale_y)

    results: list[dict] = []

    for i, step in enumerate(steps):
        delay_ms = step.get("delay_before_ms", 0) / max(speed_factor, 0.01)
        if delay_ms > 0:
            time.sleep(min(delay_ms / 1000.0, 30.0))

        step_type = step.get("type", "")
        try:
            if step_type == "tap":
                dx, dy = _scale_tap(step["x"], step["y"])
                adb.tap(dx, dy)
                adb.wait_stable()
                results.append({"seq": i + 1, "type": "tap", "x": dx, "y": dy, "status": "ok"})

            elif step_type == "input":
                adb.input_text(step["text"])
                results.append({"seq": i + 1, "type": "input", "text": step["text"], "status": "ok"})

            elif step_type == "swipe":
                dx1, dy1 = _scale_tap(step["x1"], step["y1"])
                dx2, dy2 = _scale_tap(step["x2"], step["y2"])
                adb.swipe(dx1, dy1, dx2, dy2, step.get("duration_ms", 300))
                adb.wait_stable()
                results.append({"seq": i + 1, "type": "swipe", "status": "ok"})

            elif step_type == "keyevent":
                adb.keyevent(step["key"])
                adb.wait_stable()
                results.append({"seq": i + 1, "type": "keyevent", "key": step["key"], "status": "ok"})

            else:
                results.append({"seq": i + 1, "type": step_type, "status": "skipped", "reason": "unsupported type"})

        except Exception as e:
            results.append({"seq": i + 1, "type": step_type, "status": "error", "error": str(e)})

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "error": sum(1 for r in results if r.get("status") == "error"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
    }

    return {
        "status": "ok",
        "command": "replay",
        "recording": str(path),
        "meta": meta,
        "hint": f"回放前请手动导航到录制起始页: {start_page.get('activity', '未知')}" if start_page else None,
        "summary": summary,
        "steps": results,
    }
