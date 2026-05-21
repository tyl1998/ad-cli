"""
投屏模块 - 基于 py-scrcpy-client（内嵌于 src/subsystems/mirror/scrcpy/）

两种展示模式：
  --mode window  PySide6 窗口（默认），无白边、支持拖拽缩放
  --mode web     浏览器 MJPEG 流，自动打开 http://localhost:<port>

运行环境：项目根目录 .venv（Python >= 3.10）
依赖（通过 install.sh / install.bat 一键安装）：
    av>=12,<13  adbutils>=2,<3  opencv-python>=4.8.0  numpy>=2,<3  PySide6>=6.4.0
注意：scrcpy-client 已内嵌至 src/subsystems/mirror/scrcpy/，无需额外 pip install。
"""

from __future__ import annotations

import sys
import json
import queue
import threading
import socket
import subprocess
import time
import webbrowser
from typing import Optional
from urllib.parse import urlparse, parse_qs

DEFAULT_MAX_SIZE = 1024
DEFAULT_MAX_FPS = 60
DEFAULT_BITRATE = 2_000_000  # bps
DEFAULT_WEB_PORT = 8888
DEFAULT_WINDOW_INITIAL_SCALE = 0.85
DEFAULT_WINDOW_MIN_WIDTH = 360
DEFAULT_WINDOW_MIN_HEIGHT = 640
DEFAULT_WINDOW_MAX_SCREEN_WIDTH_RATIO = 0.72
DEFAULT_WINDOW_MAX_SCREEN_HEIGHT_RATIO = 0.86


# ══════════════════════════════════════════════════════════════════
# 录制状态机
# ══════════════════════════════════════════════════════════════════

class RecordingState:
    """录制状态：捕获 tap / swipe / input / keyevent，存储为结构化 JSON。"""

    def __init__(self):
        self.steps: list[dict] = []
        self.is_recording: bool = False
        self.is_paused: bool = False
        self._last_event_time: float = 0.0
        self._text_buffer: str = ""
        self._text_buffer_start_time: float = 0.0
        # web 模式：追踪手势起点
        self._web_drag_start: tuple | None = None  # (x, y, t)
        # window 模式：追踪手势起点
        self._win_drag_start: tuple | None = None  # (x, y, t)
        # 录制起始页面（package + activity）
        self.start_page: dict = {}

    def start(self, start_page: dict | None = None) -> None:
        self.steps = []
        self.is_recording = True
        self.is_paused = False
        self._last_event_time = time.time()
        self._text_buffer = ""
        self.start_page = start_page or {}

    def pause(self) -> None:
        self._flush_text()
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False
        self._last_event_time = time.time()

    # ── 内部工具 ──────────────────────────────────────────────

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

    # ── 事件记录 ──────────────────────────────────────────────

    def add_tap(self, x: int, y: int) -> None:
        if not self.is_recording or self.is_paused:
            return
        self._flush_text()
        self._append({"type": "tap", "x": x, "y": y, "delay_before_ms": self._delay_ms()})

    def add_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
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
        self._append({"type": "keyevent", "key": key, "delay_before_ms": self._delay_ms()})

    def add_char(self, ch: str) -> None:
        if not self.is_recording or self.is_paused:
            return
        if not self._text_buffer:
            self._text_buffer_start_time = time.time()
        self._text_buffer += ch

    # ── Web 触控辅助 ─────────────────────────────────────────

    def on_web_touch(self, action: str, rx: float, ry: float, resolution: list) -> None:
        """供 web 模式 /touch 端点调用，rx/ry 为归一化比例坐标。"""
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
                dur = int((time.time() - st) * 1000)
                self.add_swipe(sx, sy, x, y, dur)
            self._web_drag_start = None

    # ── 保存 ─────────────────────────────────────────────────

    def save(self, name: str, serial: str | None, resolution: list) -> str:
        """将录制步骤写入 ~/.ad-cli/recordings/<name>_<ts>.replay.json。"""
        self._flush_text()
        from pathlib import Path
        from datetime import datetime

        recordings_dir = Path.home() / ".ad-cli" / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.replay.json"
        path = recordings_dir / filename

        data = {
            "version": "1.0",
            "meta": {
                "name": name,
                "device": serial or "",
                "resolution": resolution,
                "recorded_at": datetime.now().isoformat(),
                "start_page": self.start_page,
            },
            "steps": self.steps,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)


# ══════════════════════════════════════════════════════════════════
# 公共：构建 scrcpy Client + 帧队列
# ══════════════════════════════════════════════════════════════════

def _build_client(serial, max_size, max_fps, bitrate):
    from scrcpy import Client
    kwargs = {"max_width": max_size, "bitrate": bitrate, "max_fps": max_fps, "flip": False}
    if serial:
        kwargs["serial"] = serial
    return Client(**kwargs)


def _attach_frame_listener(client, frame_queue: queue.Queue):
    """把帧放入队列（在 scrcpy 后台线程中调用，丢弃旧帧保持低延迟）"""
    first = [False]

    def on_frame(frame):
        if frame is None:
            return
        if not first[0]:
            first[0] = True
            h, w = frame.shape[:2]
            print(json.dumps({
                "status": "ok", "command": "mirror",
                "message": f"投屏已启动 {w}×{h}",
                "resolution": [w, h],
            }), flush=True)
        if frame_queue.full():
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
        try:
            frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    client.add_listener("frame", on_frame)


def _get_screen_size() -> tuple[int, int] | None:
    """获取主屏幕尺寸，失败时返回 None。"""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "Finder" to get bounds of window of desktop',
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                parts = [part.strip() for part in result.stdout.strip().split(",")]
                if len(parts) == 4:
                    left, top, right, bottom = [int(part) for part in parts]
                    return max(1, right - left), max(1, bottom - top)
        except Exception:
            return None

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception:
        return None



def _compute_initial_window_size(frame_width: int, frame_height: int) -> tuple[int, int]:
    """
    计算默认窗口尺寸：
    - 不超过屏幕的一定比例
    - 不小于可接受的最小窗口尺寸（在屏幕允许范围内）
    - 默认以较舒适的初始缩放比例打开
    """
    screen_size = _get_screen_size()
    if not screen_size:
        return frame_width, frame_height

    screen_width, screen_height = screen_size
    max_width = max(1, int(screen_width * DEFAULT_WINDOW_MAX_SCREEN_WIDTH_RATIO))
    max_height = max(1, int(screen_height * DEFAULT_WINDOW_MAX_SCREEN_HEIGHT_RATIO))

    max_fit_scale = min(max_width / frame_width, max_height / frame_height, 1.0)
    preferred_min_scale = max(
        DEFAULT_WINDOW_MIN_WIDTH / frame_width,
        DEFAULT_WINDOW_MIN_HEIGHT / frame_height,
    )

    if max_fit_scale < preferred_min_scale:
        scale = max_fit_scale
    else:
        scale = min(max_fit_scale, DEFAULT_WINDOW_INITIAL_SCALE)
        scale = max(scale, preferred_min_scale)

    target_width = max(1, int(frame_width * scale))
    target_height = max(1, int(frame_height * scale))
    return target_width, target_height




# ══════════════════════════════════════════════════════════════════
# 模式 1：PySide6 窗口
# ══════════════════════════════════════════════════════════════════

def run_mirror(
    serial: Optional[str] = None,
    max_size: int = DEFAULT_MAX_SIZE,
    max_fps: int = DEFAULT_MAX_FPS,
    bitrate: int = DEFAULT_BITRATE,
    sharpen: bool = False,
    record_name: Optional[str] = None,
) -> None:
    """PySide6 窗口模式：无白边、支持拖拽缩放自适应、鼠标触控映射。
    record_name 非空时显示录制工具栏。"""
    try:
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QLabel, QSizePolicy,
            QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
            QInputDialog, QMessageBox,
        )
        from PySide6.QtGui import QImage, QPixmap, QMouseEvent
        from PySide6.QtCore import Qt, QTimer, Signal, QObject
    except ImportError:
        _exit_error("缺少依赖：PySide6，请运行：pip install PySide6")
        return

    try:
        import numpy as np
        from scrcpy import const as scrcpy_const
    except ImportError as e:
        _exit_error(f"缺少依赖：{e}")
        return

    client = _build_client(serial, max_size, max_fps, bitrate)
    title = f"ad-cli mirror [{serial}]" if serial else "ad-cli mirror"

    # ── Qt 信号桥（跨线程安全投递帧到主线程）─────────────────────
    class _Bridge(QObject):
        frame_ready = Signal(object)  # 传递 numpy ndarray

    bridge = _Bridge()

    def on_frame(frame):
        if frame is not None:
            bridge.frame_ready.emit(frame)

    client.add_listener("frame", on_frame)

    # ── 主窗口 ────────────────────────────────────────────────────
    app = QApplication.instance() or QApplication([])

    win = QMainWindow()
    win.setWindowTitle(title)
    win.setAttribute(Qt.WA_DeleteOnClose)

    label = QLabel()
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("background-color: black;")
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
    label.setScaledContents(False)

    # ── 中心控件（镜像画面 + 可选录制工具栏）───────────────────────
    central = QWidget()
    central_layout = QVBoxLayout(central)
    central_layout.setContentsMargins(0, 0, 0, 0)
    central_layout.setSpacing(0)
    central_layout.addWidget(label, stretch=1)

    # 录制状态机
    rec = RecordingState()

    if record_name is not None:
        toolbar = QWidget()
        toolbar.setStyleSheet(
            "background-color:#1a1a1a; border-top:1px solid #333;")
        toolbar.setFixedHeight(44)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        rec_indicator = QLabel("⚫  就绪")
        rec_indicator.setStyleSheet("color:#888; font-size:12px; min-width:90px;")

        btn_start = QPushButton("● 开始录制")
        btn_pause = QPushButton("⏸ 暂停")
        btn_stop  = QPushButton("■ 结束保存")

        _btn_style_red  = "color:#ff5555;background:#2a2a2a;border:1px solid #555;padding:4px 10px;border-radius:4px;"
        _btn_style_yel  = "color:#ffaa00;background:#2a2a2a;border:1px solid #555;padding:4px 10px;border-radius:4px;"
        _btn_style_gray = "color:#888;background:#2a2a2a;border:1px solid #444;padding:4px 10px;border-radius:4px;"

        btn_start.setStyleSheet(_btn_style_red)
        btn_pause.setStyleSheet(_btn_style_gray)
        btn_stop.setStyleSheet(_btn_style_gray)
        btn_pause.setEnabled(False)
        btn_stop.setEnabled(False)

        tb_layout.addWidget(rec_indicator)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_start)
        tb_layout.addWidget(btn_pause)
        tb_layout.addWidget(btn_stop)
        central_layout.addWidget(toolbar)

        def _on_start_record():
            # 录制前抓取当前 App/Activity 作为起点，并查询 Launcher Activity
            _start_page = {}
            try:
                import subprocess as _sp
                import re as _re
                _adb_prefix = ["adb"] + (["-s", serial] if serial else [])
                # 1. 当前前台 Activity
                _out = _sp.check_output(
                    _adb_prefix + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                    text=True, timeout=3,
                ).strip()
                _m = _re.search(r"([\w.]+)/([\w.]+)", _out)
                if _m:
                    _pkg = _m.group(1)
                    _start_page["package"] = _pkg
                    _start_page["activity"] = _m.group(2)
                    # 2. 查询该 package 的 Launcher Activity
                    try:
                        _la_out = _sp.check_output(
                            _adb_prefix + ["shell", "cmd", "package", "resolve-activity",
                                           "--brief", "-c", "android.intent.category.LAUNCHER", _pkg],
                            text=True, timeout=3,
                        ).strip()
                        _la_m = _re.search(r"([\w.]+/[\w./]+)", _la_out.split("\n")[-1])
                        if _la_m:
                            _start_page["launcher_activity"] = _la_m.group(1)
                    except Exception:
                        pass
            except Exception:
                pass
            rec.start(start_page=_start_page)
            btn_start.setEnabled(False)
            btn_pause.setEnabled(True)
            btn_pause.setStyleSheet(_btn_style_yel)
            btn_stop.setEnabled(True)
            btn_stop.setStyleSheet(_btn_style_gray)
            rec_indicator.setText("🔴  录制中")
            rec_indicator.setStyleSheet(
                "color:#ff5555;font-size:12px;font-weight:bold;min-width:90px;")

        def _on_pause_record():
            if rec.is_paused:
                rec.resume()
                btn_pause.setText("⏸ 暂停")
                rec_indicator.setText("🔴  录制中")
                rec_indicator.setStyleSheet(
                    "color:#ff5555;font-size:12px;font-weight:bold;min-width:90px;")
            else:
                rec.pause()
                btn_pause.setText("▶ 继续")
                rec_indicator.setText("⏸  已暂停")
                rec_indicator.setStyleSheet(
                    "color:#ffaa00;font-size:12px;min-width:90px;")

        def _on_stop_record():
            rec.pause()
            save_name = record_name or "recording"
            path = rec.save(save_name, serial, list(_frame_wh))
            btn_start.setEnabled(True)
            btn_pause.setEnabled(False)
            btn_pause.setStyleSheet(_btn_style_gray)
            btn_pause.setText("⏸ 暂停")
            btn_stop.setEnabled(False)
            btn_stop.setStyleSheet(_btn_style_gray)
            rec_indicator.setText("✅  已保存")
            rec_indicator.setStyleSheet(
                "color:#55ff55;font-size:12px;min-width:90px;")
            print(json.dumps({
                "status": "ok", "command": "record",
                "message": f"录制已保存: {path}",
                "path": path, "steps": len(rec.steps),
            }), flush=True)

        btn_start.clicked.connect(_on_start_record)
        btn_pause.clicked.connect(_on_pause_record)
        btn_stop.clicked.connect(_on_stop_record)

    win.setCentralWidget(central)

    # ── 计算初始窗口尺寸（等首帧到达后 resize）────────────────────
    _initialized = [False]
    _frame_wh = [1, 1]  # 设备帧原始尺寸

    def _render_frame(frame):
        if sharpen:
            import cv2 as _cv2
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
            frame = _cv2.filter2D(frame, -1, kernel)

        fh, fw = frame.shape[:2]
        _frame_wh[0], _frame_wh[1] = fw, fh

        # 首帧：按屏幕比例设置初始窗口大小
        if not _initialized[0]:
            _initialized[0] = True
            init_w, init_h = _compute_initial_window_size(fw, fh)
            win.resize(init_w, init_h)
            # Qt 居中到屏幕
            screen = app.primaryScreen().availableGeometry()
            win.move(
                screen.x() + (screen.width() - init_w) // 2,
                screen.y() + (screen.height() - init_h) // 2,
            )
            print(json.dumps({
                "status": "ok", "command": "mirror",
                "message": f"投屏已启动 {fw}×{fh}",
                "resolution": [fw, fh],
            }), flush=True)

        # 将 BGR numpy → QPixmap，让 QLabel 自动等比缩放
        image = QImage(
            frame.data,
            fw, fh,
            fw * 3,
            QImage.Format_BGR888,
        )
        pix = QPixmap.fromImage(image)
        # 缩放到 label 当前尺寸，保持宽高比，居中（黑底）
        lw, lh = label.width(), label.height()
        if lw > 0 and lh > 0:
            scaled = pix.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
        else:
            label.setPixmap(pix)

        app.processEvents()

    bridge.frame_ready.connect(_render_frame)

    # ── 鼠标事件 → 设备触控 + 录制 ──────────────────────────────────
    _drag_active = [False]

    def _label_coords_to_device(mx, my):
        """将 label 内鼠标坐标映射到设备坐标（考虑 letterbox）"""
        fw, fh = _frame_wh
        lw, lh = label.width(), label.height()
        if fw <= 0 or fh <= 0 or lw <= 0 or lh <= 0:
            return None
        scale = min(lw / fw, lh / fh)
        disp_w = int(fw * scale)
        disp_h = int(fh * scale)
        x_off = (lw - disp_w) // 2
        y_off = (lh - disp_h) // 2
        lx = mx - x_off
        ly = my - y_off
        if lx < 0 or ly < 0 or lx >= disp_w or ly >= disp_h:
            return None
        return int(lx * fw / disp_w), int(ly * fh / disp_h)

    def _mouse_press(evt: QMouseEvent):
        pos = _label_coords_to_device(evt.position().x(), evt.position().y())
        if pos:
            _drag_active[0] = True
            rec._win_drag_start = (pos[0], pos[1], time.time())
            client.control.touch(pos[0], pos[1], scrcpy_const.ACTION_DOWN)

    def _mouse_move(evt: QMouseEvent):
        if _drag_active[0]:
            pos = _label_coords_to_device(evt.position().x(), evt.position().y())
            if pos:
                client.control.touch(pos[0], pos[1], scrcpy_const.ACTION_MOVE)

    def _mouse_release(evt: QMouseEvent):
        if _drag_active[0]:
            _drag_active[0] = False
            pos = _label_coords_to_device(evt.position().x(), evt.position().y())
            if pos:
                client.control.touch(pos[0], pos[1], scrcpy_const.ACTION_UP)
                # 录制：区分 tap（点击）vs swipe（拖拽）
                if rec.is_recording and rec._win_drag_start:
                    sx, sy, st = rec._win_drag_start
                    dist = ((pos[0] - sx) ** 2 + (pos[1] - sy) ** 2) ** 0.5
                    if dist < 30:
                        rec.add_tap(sx, sy)
                    else:
                        dur = int((time.time() - st) * 1000)
                        rec.add_swipe(sx, sy, pos[0], pos[1], dur)
            rec._win_drag_start = None

    def _key_press(evt):
        """键盘输入：转发给设备，同时在录制模式下记录。"""
        from scrcpy import const as scrcpy_const
        key = evt.key()
        text = evt.text()

        # ── 特殊键 → Android keycode ──────────────────────────
        _KEYMAP = {
            Qt.Key_Backspace:  scrcpy_const.KEYCODE_DEL,
            Qt.Key_Delete:     scrcpy_const.KEYCODE_FORWARD_DEL,
            Qt.Key_Return:     scrcpy_const.KEYCODE_ENTER,
            Qt.Key_Enter:      scrcpy_const.KEYCODE_ENTER,
            Qt.Key_Escape:     scrcpy_const.KEYCODE_BACK,
            Qt.Key_Home:       scrcpy_const.KEYCODE_HOME,
            Qt.Key_Back:       scrcpy_const.KEYCODE_BACK,
            Qt.Key_Tab:        scrcpy_const.KEYCODE_TAB,
            Qt.Key_Left:       scrcpy_const.KEYCODE_DPAD_LEFT,
            Qt.Key_Right:      scrcpy_const.KEYCODE_DPAD_RIGHT,
            Qt.Key_Up:         scrcpy_const.KEYCODE_DPAD_UP,
            Qt.Key_Down:       scrcpy_const.KEYCODE_DPAD_DOWN,
        }
        if key in _KEYMAP:
            client.control.keycode(_KEYMAP[key], scrcpy_const.ACTION_DOWN)
            client.control.keycode(_KEYMAP[key], scrcpy_const.ACTION_UP)
            # 录制
            if rec.is_recording:
                _rec_key_map = {
                    Qt.Key_Backspace: "del", Qt.Key_Delete: "del",
                    Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
                    Qt.Key_Escape: "back", Qt.Key_Home: "home",
                }
                if key in _rec_key_map:
                    rec.add_key(_rec_key_map[key])
        elif text and text.isprintable():
            # 普通文本 → control.text() 直接发送（支持中文等 Unicode）
            client.control.text(text)
            if rec.is_recording:
                rec.add_char(text)

    label.mousePressEvent   = _mouse_press
    label.mouseMoveEvent    = _mouse_move
    label.mouseReleaseEvent = _mouse_release
    label.setMouseTracking(True)
    win.keyPressEvent = _key_press

    def _on_close(event):
        client.stop()
        app.quit()
        event.accept()

    win.closeEvent = _on_close

    # ── 启动 scrcpy client 并显示窗口 ────────────────────────────
    client.start(threaded=True)

    # 初始占位尺寸（首帧到达前显示黑色）
    win.resize(DEFAULT_WINDOW_MIN_WIDTH, DEFAULT_WINDOW_MIN_HEIGHT)
    win.show()

    try:
        app.exec()
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()


# ══════════════════════════════════════════════════════════════════
# 模式 2：Web 浏览器 MJPEG 流
# ══════════════════════════════════════════════════════════════════

def run_mirror_web(
    serial: Optional[str] = None,
    max_size: int = DEFAULT_MAX_SIZE,
    max_fps: int = DEFAULT_MAX_FPS,
    bitrate: int = DEFAULT_BITRATE,
    port: int = DEFAULT_WEB_PORT,
    record_name: Optional[str] = None,
) -> None:
    """
    浏览器模式：在 http://localhost:<port> 提供 MJPEG 流。
    自动打开浏览器，Ctrl+C 退出。
    """
    try:
        import cv2
        from scrcpy import Client
    except ImportError as e:
        _exit_error(f"缺少依赖：{e}")
        return

    client = _build_client(serial, max_size, max_fps, bitrate)
    fq: queue.Queue = queue.Queue(maxsize=2)
    _attach_frame_listener(client, fq)

    # ── 最新 JPEG 帧（供 HTTP 线程读取）──────────────────────────
    latest_jpeg: list[Optional[bytes]] = [None]
    jpeg_lock = threading.Lock()
    jpeg_ready = threading.Event()

    def jpeg_encoder():
        """后台线程：将帧编码为 JPEG"""
        while True:
            try:
                frame = fq.get(timeout=1.0)
            except queue.Empty:
                if not client.alive:
                    break
                continue
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                with jpeg_lock:
                    latest_jpeg[0] = buf.tobytes()
                jpeg_ready.set()

    enc_thread = threading.Thread(target=jpeg_encoder, daemon=True)

    # 录制状态机（web 模式共享）
    rec = RecordingState()
    _rec_resolution: list = [1080, 2400]  # 首帧后更新

    # ── 极简 HTTP 服务（无需 Flask/aiohttp）──────────────────────
    _RECORD_TOOLBAR = """
  <div id="rec-bar" style="position:fixed;bottom:16px;right:16px;
    background:rgba(20,20,20,0.88);border:1px solid #444;border-radius:8px;
    display:flex;flex-direction:column;align-items:stretch;
    padding:8px 10px;gap:6px;z-index:999;min-width:130px;
    backdrop-filter:blur(4px);">
    <span id="rec-status" style="color:#888;font-size:11px;text-align:center;">⚫ 就绪</span>
    <button onclick="recStart()" id="btn-start"
      style="color:#ff5555;background:#2a2a2a;border:1px solid #555;padding:5px 8px;border-radius:4px;cursor:pointer;font-size:12px;">
      ● 开始录制</button>
    <button onclick="recPause()" id="btn-pause" disabled
      style="color:#888;background:#2a2a2a;border:1px solid #444;padding:5px 8px;border-radius:4px;cursor:pointer;font-size:12px;">
      ⏸ 暂停</button>
    <button onclick="recStop()" id="btn-stop" disabled
      style="color:#888;background:#2a2a2a;border:1px solid #444;padding:5px 8px;border-radius:4px;cursor:pointer;font-size:12px;">
      ■ 结束保存</button>
  </div>
  <script>
    let _recPaused = false;
    function recStart() {{
      fetch('/record/start').then(() => {{
        document.getElementById('rec-status').textContent = '🔴 录制中';
        document.getElementById('rec-status').style.color = '#ff5555';
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-pause').disabled = false;
        document.getElementById('btn-stop').disabled = false;
        _recPaused = false;
      }});
    }}
    function recPause() {{
      fetch('/record/pause').then(() => {{
        _recPaused = !_recPaused;
        document.getElementById('btn-pause').textContent = _recPaused ? '▶ 继续' : '⏸ 暂停';
        document.getElementById('rec-status').textContent = _recPaused ? '⏸ 已暂停' : '🔴 录制中';
        document.getElementById('rec-status').style.color = _recPaused ? '#ffaa00' : '#ff5555';
      }});
    }}
    function recStop() {{
      fetch('/record/stop').then(r => r.json()).then(d => {{
        document.getElementById('rec-status').textContent = '✅ 已保存';
        document.getElementById('rec-status').style.color = '#55ff55';
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-pause').disabled = true;
        document.getElementById('btn-stop').disabled = true;
        _recPaused = false;
        document.getElementById('btn-pause').textContent = '⏸ 暂停';
        alert('录制已保存\\n' + (d.path || ''));
      }});
    }}
  </script>""" if record_name is not None else ""

    HTML = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ad-cli mirror</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box }}
    body {{ background:#111; display:flex; justify-content:center; align-items:center;
           height:100vh; overflow:hidden }}
    img {{ max-height:100vh; max-width:100vw; object-fit:contain; cursor:pointer; user-select:none }}
  </style>
</head>
<body>
  <img id="mirror" src="/stream" alt="mirror" draggable="false">
  {_RECORD_TOOLBAR}
  <script>
    const img = document.getElementById('mirror');
    img.onerror = () => setTimeout(() => img.src = '/stream?' + Date.now(), 1000);

    function imgToDevice(clientX, clientY) {{
      const r = img.getBoundingClientRect();
      const rx = (clientX - r.left) / r.width;
      const ry = (clientY - r.top) / r.height;
      if (rx < 0 || ry < 0 || rx > 1 || ry > 1) return null;
      return {{ x: rx, y: ry }};
    }}
    function sendTouch(action, clientX, clientY) {{
      const pos = imgToDevice(clientX, clientY);
      if (!pos) return;
      fetch(`/touch?action=${{action}}&rx=${{pos.x.toFixed(5)}}&ry=${{pos.y.toFixed(5)}}`);
    }}

    let dragging = false;
    img.addEventListener('mousedown', e => {{ dragging = true; sendTouch('down', e.clientX, e.clientY); e.preventDefault(); }});
    document.addEventListener('mousemove', e => {{ if (dragging) sendTouch('move', e.clientX, e.clientY); }});
    document.addEventListener('mouseup',   e => {{ if (dragging) {{ dragging = false; sendTouch('up', e.clientX, e.clientY); }} }});

    img.addEventListener('touchstart', e => {{ const t = e.touches[0]; sendTouch('down', t.clientX, t.clientY); e.preventDefault(); }}, {{passive:false}});
    img.addEventListener('touchmove',  e => {{ const t = e.touches[0]; sendTouch('move', t.clientX, t.clientY); e.preventDefault(); }}, {{passive:false}});
    img.addEventListener('touchend',   e => {{ const t = e.changedTouches[0]; sendTouch('up', t.clientX, t.clientY); }});

    // 键盘输入：点击投屏区域后获取焦点，监听键盘并转发给设备
    document.addEventListener('click', e => {{ if (e.target === img) document.body.focus(); }});
    document.body.setAttribute('tabindex', '0');
    document.body.addEventListener('keydown', e => {{
      const specialKeys = {{
        'Backspace': 'del', 'Enter': 'enter', 'Escape': 'back',
        'Home': 'home', 'Tab': 'tab',
      }};
      if (specialKeys[e.key]) {{
        fetch('/input?key=' + specialKeys[e.key]);
        e.preventDefault();
      }} else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {{
        fetch('/input?text=' + encodeURIComponent(e.key));
        e.preventDefault();
      }}
    }});
  </script>
</body>
</html>"""

    def handle_client(conn: socket.socket):
        try:
            data = conn.recv(1024).decode("utf-8", errors="ignore")
            path = data.split(" ")[1] if " " in data else "/"

            if path == "/" or path.startswith("/?"):
                body = HTML.encode()
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
                )
            elif path.startswith("/record/"):
                # 录制控制端点
                action_path = path.split("?")[0].rstrip("/")
                resp_body = b"{}"
                if action_path == "/record/start":
                    _start_page = {}
                    try:
                        import subprocess as _sp
                        import re as _re2
                        _adb_pfx = ["adb"] + (["-s", serial] if serial else [])
                        _out = _sp.check_output(
                            _adb_pfx + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                            text=True, timeout=3,
                        ).strip()
                        _m2 = _re2.search(r"([\w.]+)/([\w.]+)", _out)
                        if _m2:
                            _pkg2 = _m2.group(1)
                            _start_page["package"] = _pkg2
                            _start_page["activity"] = _m2.group(2)
                            try:
                                _la2 = _sp.check_output(
                                    _adb_pfx + ["shell", "cmd", "package", "resolve-activity",
                                                "--brief", "-c", "android.intent.category.LAUNCHER", _pkg2],
                                    text=True, timeout=3,
                                ).strip()
                                _lm2 = _re2.search(r"([\w.]+/[\w./]+)", _la2.split("\n")[-1])
                                if _lm2:
                                    _start_page["launcher_activity"] = _lm2.group(1)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    rec.start(start_page=_start_page)
                elif action_path == "/record/pause":
                    if rec.is_paused:
                        rec.resume()
                    else:
                        rec.pause()
                elif action_path == "/record/stop":
                    rec.pause()
                    save_name = record_name or "recording"
                    saved_path = rec.save(save_name, serial, _rec_resolution)
                    resp_body = json.dumps({
                        "status": "ok", "path": saved_path,
                        "steps": len(rec.steps),
                    }).encode()
                    print(json.dumps({
                        "status": "ok", "command": "record",
                        "message": f"录制已保存: {saved_path}",
                        "path": saved_path, "steps": len(rec.steps),
                    }), flush=True)
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Content-Length: " + str(len(resp_body)).encode() + b"\r\n\r\n"
                    + resp_body
                )
            elif path.startswith("/touch"):
                # /touch?action=down|move|up&rx=0.5&ry=0.5 (rx/ry 为比例坐标)
                try:
                    from scrcpy import const as scrcpy_const
                    qs = parse_qs(urlparse(path).query)
                    action_str = qs.get("action", ["down"])[0]
                    rx = float(qs.get("rx", ["0"])[0])
                    ry = float(qs.get("ry", ["0"])[0])
                    with jpeg_lock:
                        res = client.resolution  # (w, h)
                    dev_x = int(rx * res[0])
                    dev_y = int(ry * res[1])
                    action_map = {
                        "down": scrcpy_const.ACTION_DOWN,
                        "move": scrcpy_const.ACTION_MOVE,
                        "up": scrcpy_const.ACTION_UP,
                    }
                    if action_str in action_map:
                        client.control.touch(dev_x, dev_y, action_map[action_str])
                    # 同步录制
                    if record_name is not None:
                        rec.on_web_touch(action_str, rx, ry,
                                         list(res) if res else _rec_resolution)
                except Exception:
                    pass
                conn.sendall(b"HTTP/1.1 204 No Content\r\n\r\n")
            elif path.startswith("/input"):
                # /input?text=hello  或  /input?key=back|enter|del|home
                try:
                    from scrcpy import const as scrcpy_const
                    qs = parse_qs(urlparse(path).query)
                    if "text" in qs:
                        client.control.text(qs["text"][0])
                        if rec.is_recording:
                            for ch in qs["text"][0]:
                                rec.add_char(ch)
                    elif "key" in qs:
                        _KEY_MAP = {
                            "back":  scrcpy_const.KEYCODE_BACK,
                            "enter": scrcpy_const.KEYCODE_ENTER,
                            "del":   scrcpy_const.KEYCODE_DEL,
                            "home":  scrcpy_const.KEYCODE_HOME,
                            "tab":   scrcpy_const.KEYCODE_TAB,
                        }
                        kc = _KEY_MAP.get(qs["key"][0])
                        if kc:
                            client.control.keycode(kc, scrcpy_const.ACTION_DOWN)
                            client.control.keycode(kc, scrcpy_const.ACTION_UP)
                            if rec.is_recording:
                                rec.add_key(qs["key"][0])
                except Exception:
                    pass
                conn.sendall(b"HTTP/1.1 204 No Content\r\n\r\n")
            elif path.startswith("/stream"):
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
                    b"Cache-Control: no-cache\r\n\r\n"
                )
                while client.alive:
                    jpeg_ready.wait(timeout=2.0)
                    jpeg_ready.clear()
                    with jpeg_lock:
                        jpg = latest_jpeg[0]
                    if jpg is None:
                        continue
                    try:
                        conn.sendall(
                            b"--frame\r\nContent-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
                            + jpg + b"\r\n"
                        )
                    except (BrokenPipeError, ConnectionResetError):
                        break
            else:
                conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(8)
    srv.settimeout(1.0)

    def http_server():
        while client.alive:
            try:
                conn, _ = srv.accept()
                threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    try:
        client.start(threaded=True)
        enc_thread.start()

        url = f"http://localhost:{port}"
        print(json.dumps({
            "status": "ok", "command": "mirror",
            "message": f"浏览器投屏: {url}  （Ctrl+C 退出）",
            "url": url,
        }), flush=True)

        # 等首帧就绪后再开浏览器，体验更好
        jpeg_ready.wait(timeout=10.0)
        threading.Thread(target=lambda: (time.sleep(0.3), webbrowser.open(url)), daemon=True).start()

        threading.Thread(target=http_server, daemon=True).start()

        # 主线程阻塞
        while client.alive:
            time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        srv.close()


# ══════════════════════════════════════════════════════════════════
# 错误输出
# ══════════════════════════════════════════════════════════════════

def _exit_error(msg: str) -> None:
    print(json.dumps({
        "status": "error", "command": "mirror",
        "code": "DEPENDENCY_ERROR", "message": msg,
    }))
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════
# 直接运行入口
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ad-cli 投屏（py-scrcpy-client）")
    ap.add_argument("--serial", "-s", default=None, help="设备序列号")
    ap.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE, help="最大分辨率，默认 1024")
    ap.add_argument("--max-fps", type=int, default=DEFAULT_MAX_FPS, help="最大帧率，默认 60")
    ap.add_argument("--bitrate", type=int, default=DEFAULT_BITRATE, help="视频码率 bps")
    ap.add_argument("--mode", choices=["window", "web"], default="window",
                    help="展示模式：window=OpenCV窗口（默认），web=浏览器MJPEG流")
    ap.add_argument("--port", type=int, default=DEFAULT_WEB_PORT, help="web 模式端口，默认 8888")
    ap.add_argument("--sharpen", action="store_true", default=False, help="开启画面锐化（默认关闭）")
    ap.add_argument("--record", default=None, metavar="NAME", help="录制模式，指定录制名称")
    ns = ap.parse_args()

    if ns.mode == "web":
        run_mirror_web(serial=ns.serial, max_size=ns.max_size, max_fps=ns.max_fps,
                       bitrate=ns.bitrate, port=ns.port, record_name=ns.record)
    else:
        run_mirror(serial=ns.serial, max_size=ns.max_size, max_fps=ns.max_fps,
                   bitrate=ns.bitrate, sharpen=ns.sharpen, record_name=ns.record)


