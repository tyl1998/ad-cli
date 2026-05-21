"""
录制状态机 — RecordingState

捕获用户在投屏窗口内的 tap / swipe / input / keyevent，
记录真实时间间隔，最终导出为结构化 replay JSON。

保存路径：~/.ad-cli/recordings/<name>_<timestamp>.replay.json
"""
from __future__ import annotations

import json
import time
from typing import Optional


class RecordingState:
    """录制状态：捕获 tap / swipe / input / keyevent，存储为结构化 JSON。"""

    def __init__(self):
        self.steps: list[dict] = []
        self.is_recording: bool = False
        self.is_paused: bool = False
        self._last_event_time: float = 0.0
        self._text_buffer: str = ""
        self._text_buffer_start_time: float = 0.0
        self._web_drag_start: Optional[tuple] = None   # (x, y, t)
        self._win_drag_start: Optional[tuple] = None   # (x, y, t)

    def start(self) -> None:
        self.steps = []
        self.is_recording = True
        self.is_paused = False
        self._last_event_time = time.time()
        self._text_buffer = ""

    def pause(self) -> None:
        self._flush_text()
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False
        self._last_event_time = time.time()

    # ── 内部工具 ──────────────────────────────────────────────────

    def _flush_text(self) -> None:
        if not self._text_buffer:
            return
        delay = max(0, int((self._text_buffer_start_time - self._last_event_time) * 1000))
        self.steps.append({
            "seq": len(self.steps) + 1,
            "type": "input",
            "text": self._text_buffer,
            "delay_before_ms": delay,
        })
        self._last_event_time = time.time()
        self._text_buffer = ""

    def _delay_ms(self) -> int:
        now = time.time()
        d = max(0, int((now - self._last_event_time) * 1000))
        self._last_event_time = now
        return d

    def _append(self, step: dict) -> None:
        step["seq"] = len(self.steps) + 1
        self.steps.append(step)

    # ── 事件录入 ──────────────────────────────────────────────────

    def add_tap(self, x: int, y: int) -> None:
        if not self.is_recording or self.is_paused:
            return
        self._flush_text()
        self._append({"type": "tap", "x": x, "y": y,
                       "delay_before_ms": self._delay_ms()})

    def add_swipe(self, x1: int, y1: int, x2: int, y2: int,
                  duration_ms: int) -> None:
        if not self.is_recording or self.is_paused:
            return
        self._flush_text()
        self._append({
            "type": "swipe",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "duration_ms": duration_ms,
            "delay_before_ms": self._delay_ms(),
        })

    def add_key(self, key: str) -> None:
        if not self.is_recording or self.is_paused:
            return
        self._flush_text()
        self._append({"type": "keyevent", "key": key,
                       "delay_before_ms": self._delay_ms()})

    def add_char(self, ch: str) -> None:
        if not self.is_recording or self.is_paused:
            return
        if not self._text_buffer:
            self._text_buffer_start_time = time.time()
        self._text_buffer += ch

    # ── Web 触控辅助 ──────────────────────────────────────────────

    def on_web_touch(self, action: str, rx: float, ry: float,
                     resolution: list) -> None:
        """供 web /touch 端点调用，rx/ry 为归一化比例坐标。"""
        if not self.is_recording or self.is_paused:
            return
        x = int(rx * resolution[0])
        y = int(ry * resolution[1])
        if action == "down":
            self._web_drag_start = (x, y, time.time())
        elif action == "up" and self._web_drag_start:
            sx, sy, st = self._web_drag_start
            dist = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
            if dist < 30:
                self.add_tap(sx, sy)
            else:
                self.add_swipe(sx, sy, x, y, int((time.time() - st) * 1000))
            self._web_drag_start = None

    # ── 保存 ──────────────────────────────────────────────────────

    def save(self, name: str, serial: Optional[str],
             resolution: list) -> str:
        """写入 ~/.ad-cli/recordings/<name>_<ts>.replay.json，返回路径。"""
        self._flush_text()
        from pathlib import Path
        from datetime import datetime

        recordings_dir = Path.home() / ".ad-cli" / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = recordings_dir / f"{name}_{ts}.replay.json"
        data = {
            "version": "1.0",
            "meta": {
                "name": name,
                "device": serial or "",
                "resolution": resolution,
                "recorded_at": datetime.now().isoformat(),
            },
            "steps": self.steps,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)
