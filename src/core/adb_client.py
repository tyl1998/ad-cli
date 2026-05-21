"""
ADB 底层封装模块
所有 adb 命令调用都通过此模块，统一处理连接异常
"""
import subprocess
import time
import re
from output import err_disconnected


class ADBError(Exception):
    pass


class ADBClient:
    def __init__(self, serial: str = None):
        """
        serial: 指定设备序列号，None 时使用默认连接设备
        """
        self.serial = serial
        self._base_cmd = ["adb"]
        if serial:
            self._base_cmd += ["-s", serial]

    # ── 基础执行 ─────────────────────────────────────────────

    def run(self, *args, timeout=10) -> str:
        """执行 adb 命令，返回 stdout 字符串，失败抛 ADBError"""
        cmd = self._base_cmd + list(args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0 and result.stderr:
                raise ADBError(result.stderr.strip())
            return result.stdout.strip()
        except FileNotFoundError:
            raise ADBError("找不到 adb 命令，请确认已安装 Android SDK Platform Tools")
        except subprocess.TimeoutExpired:
            raise ADBError(f"adb 命令超时（{timeout}s）")

    def shell(self, *args, timeout=10) -> str:
        """执行 adb shell 命令"""
        return self.run("shell", *args, timeout=timeout)

    # ── 设备检测 ─────────────────────────────────────────────

    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        try:
            output = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            ).stdout
            devices = [
                line.split()[0]
                for line in output.splitlines()[1:]
                if line.strip() and "device" in line and "offline" not in line
            ]
            if self.serial:
                return self.serial in devices
            return len(devices) > 0
        except Exception:
            return False

    def get_serial(self) -> str | None:
        """获取当前连接设备序列号"""
        try:
            output = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            ).stdout
            for line in output.splitlines()[1:]:
                if line.strip() and "device" in line and "offline" not in line:
                    return line.split()[0]
        except Exception:
            pass
        return None

    # ── 设备信息 ─────────────────────────────────────────────

    def get_device_info(self) -> dict:
        """获取设备基本信息（一次 getprop 全量获取，减少 ADB 往返）"""
        # 一次读取所有属性
        raw = self.shell("getprop")
        props_raw: dict[str, str] = {}
        for line in raw.splitlines():
            m = re.match(r"\[([^\]]+)\]:\s*\[([^\]]*)\]", line)
            if m:
                props_raw[m.group(1)] = m.group(2)

        props = {
            "model":     props_raw.get("ro.product.model", ""),
            "brand":     props_raw.get("ro.product.brand", ""),
            "android":   props_raw.get("ro.build.version.release", ""),
            "api_level": props_raw.get("ro.build.version.sdk", ""),
            "serial":    self.get_serial() or "",
        }
        # 分辨率仍需单独获取
        size_raw = self.shell("wm", "size")  # e.g. "Physical size: 1080x2400"
        match = re.search(r"(\d+)x(\d+)", size_raw)
        if match:
            props["resolution"] = f"{match.group(1)}x{match.group(2)}"
        return props

    # ── 页面信息 ─────────────────────────────────────────────

    def get_current_page(self) -> dict:
        """获取当前页面的包名和 Activity。

        兼容各 Android 版本：
          - Android < 12：mCurrentFocus
          - Android 12+：mCurrentFocus 消失，改用 mFocusedApp / mTopActivityComponent
        """
        # 一次 dump 同时覆盖三种字段，避免多次 shell 调用
        output = self.shell("dumpsys", "window", timeout=10)

        # 优先匹配 mCurrentFocus（Android < 12）
        # e.g. mCurrentFocus=Window{... com.example/com.example.MainActivity}
        m = re.search(r"mCurrentFocus=Window\{[^}]*\s+([\w.]+)/([\w.$]+)", output)
        if m:
            return {"package": m.group(1), "activity": m.group(2)}

        # Fallback: mFocusedApp（Android 12+）
        # e.g. mFocusedApp=AppWindowToken{... token=Token{... ActivityRecord{... com.example/.MainActivity}}}
        m = re.search(r"mFocusedApp=.*?([\w.]+)/([\w.$]+)", output)
        if m:
            return {"package": m.group(1), "activity": m.group(2)}

        # Fallback: mTopActivityComponent（部分厂商 ROM）
        m = re.search(r"mTopActivityComponent=([\w.]+)/([\w.$]+)", output)
        if m:
            return {"package": m.group(1), "activity": m.group(2)}

        return {"package": "", "activity": ""}

    # ── UI dump ──────────────────────────────────────────────

    def dump_ui(self, remote_path="/sdcard/_ad_cli_ui.xml") -> str:
        """dump 当前 UI 树，返回 XML 字符串"""
        self.shell("uiautomator", "dump", remote_path, timeout=15)
        xml_content = self.run("shell", "cat", remote_path, timeout=10)
        return xml_content

    # ── 输入操作 ─────────────────────────────────────────────

    def tap(self, x: int, y: int):
        """点击坐标"""
        self.shell("input", "tap", str(x), str(y))

    def input_text(self, text: str):
        """输入文字（需要先 tap 聚焦输入框）"""
        # 转义 Android shell 敏感字符
        escaped = text.replace(" ", "%s")
        for ch in "&<>|;$`\"'()\\":
            escaped = escaped.replace(ch, f"\\{ch}")
        self.shell("input", "text", escaped)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """滑动"""
        self.shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))

    def keyevent(self, key: str):
        """发送按键事件"""
        key_map = {
            "back":   "4",
            "home":   "3",
            "enter":  "66",
            "del":    "67",
            "menu":   "82",
        }
        code = key_map.get(key.lower(), key)
        self.shell("input", "keyevent", code)

    # ── 截图 ─────────────────────────────────────────────────

    def screenshot(self, local_path: str, remote_path="/sdcard/_ad_cli_screen.png"):
        """截图并保存到本地，完成后删除手机上的临时文件"""
        self.shell("screencap", remote_path, timeout=10)
        self.run("pull", remote_path, local_path, timeout=15)
        # 删除手机上的临时截图，避免占用存储
        try:
            self.shell("rm", "-f", remote_path)
        except Exception:
            pass

    # ── App 操作 ─────────────────────────────────────────────

    def launch_app(self, package: str):
        """启动 App（通过 monkey 方式，兼容性好）"""
        self.shell("monkey", "-p", package, "-c",
                   "android.intent.category.LAUNCHER", "1", timeout=10)

    def stop_app(self, package: str):
        """强制停止 App"""
        self.shell("am", "force-stop", package)

    def install_apk(self, apk_path: str):
        """安装 APK"""
        self.run("install", "-r", apk_path, timeout=120)

    def is_app_installed(self, package: str) -> bool:
        """检查 App 是否已安装"""
        output = self.shell("pm", "list", "packages", package)
        return f"package:{package}" in output

    def is_app_running(self, package: str) -> bool:
        """检查 App 是否在前台运行"""
        page = self.get_current_page()
        return page.get("package") == package

    def get_app_version(self, package: str) -> str:
        """获取 App 版本号"""
        output = self.shell("dumpsys", "package", package, "|", "grep", "versionName")
        match = re.search(r"versionName=([\S]+)", output)
        return match.group(1) if match else ""

    def list_launcher_apps(self) -> list[dict]:
        """列出所有有桌面图标的可启动 App"""
        # 获取所有可启动包名（去重有序）
        output = self.shell(
            "cmd", "package", "query-activities",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            timeout=15
        )
        packages = []
        seen = set()
        for line in output.splitlines():
            m = re.search(r"packageName=([\w.]+)", line)
            if m:
                pkg = m.group(1)
                if pkg not in seen:
                    seen.add(pkg)
                    packages.append(pkg)

        # 一次性获取所有包的 label（dumpsys packages 全量）
        label_map = self._get_all_labels()

        return [
            {"package": pkg, "name": label_map.get(pkg, pkg.split(".")[-1].capitalize())}
            for pkg in packages
        ]

    def _get_all_labels(self) -> dict:
        """一次性获取所有 App 的 nonLocalizedLabel，返回 {package: name}"""
        try:
            output = self.shell("dumpsys", "package", "packages", timeout=30)
        except Exception:
            return {}

        label_map = {}
        current_pkg = None
        for line in output.splitlines():
            pkg_m = re.search(r"Package \[([\w.]+)\]", line)
            if pkg_m:
                current_pkg = pkg_m.group(1)
                continue
            if current_pkg:
                label_m = re.search(r"nonLocalizedLabel=([^\s]+)", line)
                if label_m and label_m.group(1) != "null":
                    label_map[current_pkg] = label_m.group(1)
        return label_map

    # ── 等待页面稳定 ─────────────────────────────────────────

    def wait_stable(self, timeout_ms: int = 2000, interval_ms: int = 200) -> bool:
        """等待页面稳定（检测 Activity 不再变化）。返回 True 表示稳定，False 表示超时放弃"""
        deadline = time.time() + timeout_ms / 1000
        last_page = self.get_current_page()
        time.sleep(interval_ms / 1000)
        while time.time() < deadline:
            current_page = self.get_current_page()
            if current_page == last_page:
                return True
            last_page = current_page
            time.sleep(interval_ms / 1000)
        return False  # 超时，调用方可根据需要决定是否继续
