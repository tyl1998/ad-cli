"""
Ad-CLI Agent HTTP 客户端

通过 adb forward tcp:8899 tcp:8899 → http://localhost:8899 与 Agent App 通信。
提供：
  - AgentClient.get_elements() → /elements?ocr=&screenshot=
  - AgentClient.get_device()   → /device
  - AgentClient.get_page()     → /page
  - AgentClient.click()        → /click
  - AgentClient.input_text()   → /input
  - AgentClient.swipe()        → /swipe
  - AgentClient.back()         → /back
  - AgentClient.home()         → /home
  - AgentClient.keyevent()     → /keyevent
  - AgentClient.screenshot()   → /screenshot
  - AgentClient.is_ready()     → 判断 Agent 是否就绪
"""
from __future__ import annotations

import base64
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import json
import os

DEFAULT_PORT = 8899
AGENT_PACKAGE = "com.anonymous.x7644075776060555307"
AGENT_RECEIVER = f"{AGENT_PACKAGE}/com.adcli.agent.AgentBroadcastReceiver"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".ad-cli", "agent")
GITHUB_REPO = "tyl1998/ad-cli-app"


class AgentError(Exception):
    pass


class AgentClient:
    """Agent App HTTP API 客户端（通过 adb forward 本地端口访问）。"""

    def __init__(self, port: int = DEFAULT_PORT, serial: str | None = None):
        self.port = port
        self.serial = serial
        self._base_url = f"http://localhost:{port}"

    # ── 端口转发 ─────────────────────────────────────────────

    def setup_forward(self) -> bool:
        """执行 adb forward tcp:<port> tcp:<port>，返回是否成功。"""
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += ["forward", f"tcp:{self.port}", f"tcp:{self.port}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    # ── 服务状态 ─────────────────────────────────────────────

    def is_ready(self) -> bool:
        """检查 Agent HTTP Server 是否就绪（serviceRunning=true）。"""
        try:
            data = self._get("/device", timeout=3)
            return bool(data.get("serviceRunning"))
        except Exception:
            return False

    def try_start_via_broadcast(self):
        """尝试通过 ADB 广播启动 HTTP Server（无 HTTP 连接时使用）。"""
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += [
            "shell", "am", "broadcast",
            "-a", "com.adcli.agent.START_SERVER",
            "-n", AGENT_RECEIVER,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            pass

    # ── 核心 API ─────────────────────────────────────────────

    def get_device(self) -> dict:
        """/device — 设备信息及服务状态。"""
        return self._get("/device")

    def get_page(self) -> dict:
        """/page — 当前前台包名。"""
        return self._get("/page")

    def get_elements(
        self,
        ocr: bool = False,
        screenshot: bool = False,
    ) -> dict:
        """/elements — 获取当前页面 UI 元素。

        Returns
        -------
        dict 包含 success / count / captureMode / elements / hint / screenshot(base64) 等字段。
        """
        params: dict[str, str] = {}
        if ocr:
            params["ocr"] = "1"
        if screenshot:
            params["screenshot"] = "1"
        qs = f"?{urllib.parse.urlencode(params)}" if params else ""
        return self._get(f"/elements{qs}")

    def click(self, x: int | float, y: int | float) -> dict:
        """/click?x=&y= — 坐标点击。"""
        return self._get(f"/click?x={x}&y={y}")

    def click_by_selector(self, selector: str, value: str) -> dict:
        """/click?selector=&value= — 选择器点击（仅原生元素）。"""
        qs = urllib.parse.urlencode({"selector": selector, "value": value})
        return self._get(f"/click?{qs}")

    def input_text(self, text: str) -> dict:
        """/input?text= — 输入文本（替换全部内容）。"""
        qs = urllib.parse.urlencode({"text": text})
        return self._get(f"/input?{qs}")

    def input_by_selector(self, selector: str, value: str, text: str) -> dict:
        """/input?selector=&value=&text= — 定位后输入。"""
        qs = urllib.parse.urlencode({"selector": selector, "value": value, "text": text})
        return self._get(f"/input?{qs}")

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
    ) -> dict:
        """/swipe — 滑动手势（300ms）。"""
        qs = urllib.parse.urlencode({
            "startX": start_x, "startY": start_y,
            "endX": end_x, "endY": end_y,
        })
        return self._get(f"/swipe?{qs}")

    def back(self) -> dict:
        """/back — 模拟返回键。"""
        return self._get("/back")

    def home(self) -> dict:
        """/home — 模拟 Home 键。"""
        return self._get("/home")

    def keyevent(self, key_code: int) -> dict:
        """/keyevent?key= — 发送 Android KeyCode。"""
        return self._get(f"/keyevent?key={key_code}")

    def screenshot(self) -> bytes:
        """/screenshot — 返回 PNG bytes。"""
        data = self._get("/screenshot", timeout=15)
        if not data.get("success"):
            raise AgentError(data.get("error", "Screenshot failed"))
        return base64.b64decode(data["data"])

    # ── 内部 HTTP ────────────────────────────────────────────

    def _get(self, path: str, timeout: int = 10) -> dict:
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "ad-cli"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise AgentError(f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise AgentError(f"Connection failed to Agent ({url}): {e.reason}")
        except Exception as e:
            raise AgentError(f"Agent request error: {e}")
