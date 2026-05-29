"""Agent 管理命令：install / setup / status / diagnose

agent install   — 下载并安装 Agent APK，引导开启无障碍服务
agent setup     — 端口转发 + 服务就绪确认
agent status    — 查询 Agent 运行状态
agent diagnose  — 一键排查 Agent 未就绪的原因并给出修复建议
"""
from __future__ import annotations

import os
import ssl
import subprocess
import sys
import time
import urllib.request
import json

from output import ok, error

GITHUB_REPO = "tyl1998/ad-cli-app"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".ad-cli", "agent")
DEFAULT_PORT = 8899
AGENT_PACKAGE = "com.anonymous.x7644075776060555307"
AGENT_RECEIVER = f"{AGENT_PACKAGE}/com.adcli.agent.AgentBroadcastReceiver"


# ── SSL 证书修复 ──────────────────────────────────────────────────

def _ssl_context() -> ssl.SSLContext:
    """创建带 CA 证书验证的 SSL context。

    macOS + Homebrew OpenSSL 环境下系统 CA bundle 可能缺失，
    优先使用 certifi 包提供的 CA 证书。
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

# ── 工具函数 ──────────────────────────────────────────────────────

def _run_adb(*args, serial: str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """执行 adb 命令，返回 (returncode, stdout, stderr)。"""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"adb command timeout ({timeout}s)"
    except FileNotFoundError:
        return -1, "", "adb not found. Please install Android SDK Platform Tools."


def _get_latest_release() -> dict | None:
    """从 GitHub API 获取最新 Release 信息。"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "ad-cli"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _download_apk(url: str, dest: str) -> bool:
    """下载 APK 到 dest，支持断点续传，显示实时进度（stderr），返回是否成功。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    existing_size = os.path.getsize(dest) if os.path.exists(dest) else 0

    headers: dict[str, str] = {"User-Agent": "ad-cli"}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"
        print(f"  续传: {url} (已有 {existing_size / 1024 / 1024:.1f} MB)", file=sys.stderr)
    else:
        print(f"  下载: {url}", file=sys.stderr)

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as resp:
            # 总大小：206 响应用 Content-Range，200 响应（新下载）用 Content-Length
            if resp.status == 206:
                # Content-Range: bytes 1234-567890/567891
                cr = resp.headers.get("Content-Range", "")
                total_size = existing_size + int(resp.headers.get("Content-Length", 0))
                if "/" in cr:
                    try:
                        total_size = int(cr.rsplit("/", 1)[-1])
                    except ValueError:
                        pass
            else:
                total_size = int(resp.headers.get("Content-Length", 0))
                existing_size = 0  # 服务器不支持续传，从头开始

            downloaded = existing_size
            mode = "ab" if existing_size > 0 else "wb"
            with open(dest, mode) as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = downloaded / total_size * 100
                        mb_done = downloaded / 1024 / 1024
                        mb_total = total_size / 1024 / 1024
                        bar_width = 30
                        filled = int(bar_width * downloaded / total_size)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        print(
                            f"\r  下载中  [{bar}] {pct:.0f}%  {mb_done:.1f}/{mb_total:.1f} MB",
                            end="", file=sys.stderr, flush=True,
                        )
            if total_size > 0:
                print("", file=sys.stderr)  # 换行
    except Exception as e:
        print(f"\n  下载异常: {type(e).__name__}: {e}", file=sys.stderr)
        # 保留已下载的部分，下次可续传
        return False
    return True


def _wait_for_ready(port: int, serial: str | None, timeout_s: int = 60) -> bool:
    """等待 Agent HTTP Server 就绪，返回是否成功。"""
    from core.agent_client import AgentClient, AgentError
    client = AgentClient(port=port, serial=serial)

    # 确保端口转发
    if not client.setup_forward():
        return False

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if client.is_ready():
            return True
        # 尝试广播启动
        client.try_start_via_broadcast()
        time.sleep(2)
    return False


# ── 命令实现 ──────────────────────────────────────────────────────

def cmd_agent_install(
    serial: str | None = None,
    version: str | None = None,
    force: bool = False,
    port: int = DEFAULT_PORT,
) -> dict:
    """下载并安装 Agent APK，完成后引导用户开启无障碍服务。"""

    # 1. 获取 Release 信息
    release = _get_latest_release()
    if not release:
        return error(
            "agent install",
            "GITHUB_API_ERROR",
            f"无法从 GitHub 获取 Release 信息（{GITHUB_REPO}），请检查网络连接",
        )

    tag = release.get("tag_name", "unknown")
    ver = tag.lstrip("v")
    assets = release.get("assets", [])
    apk_asset = next((a for a in assets if a["name"].endswith(".apk")), None)
    if not apk_asset:
        return error("agent install", "APK_NOT_FOUND", f"Release {tag} 中未找到 APK 文件")

    cached_apk = os.path.join(CACHE_DIR, f"ad-cli-agent-{ver}.apk")

    # 2. 下载（未缓存 / 大小不完整 / --force 时触发，支持断点续传）
    expected_size = apk_asset.get("size", 0)
    has_file = os.path.exists(cached_apk)
    file_size = os.path.getsize(cached_apk) if has_file else 0
    needs_download = not has_file or force or file_size < expected_size
    if needs_download:
        size_mb = expected_size / 1024 / 1024
        download_url = apk_asset["browser_download_url"]
        success = _download_apk(download_url, cached_apk)
        if not success:
            return error(
                "agent install",
                "DOWNLOAD_FAILED",
                f"APK 下载失败：{download_url}",
            )
    else:
        size_mb = file_size / 1024 / 1024

    # 3. 安装 APK
    rc, stdout, stderr = _run_adb("install", "-r", cached_apk, serial=serial, timeout=120)
    if rc != 0:
        return error("agent install", "INSTALL_FAILED", f"adb install 失败: {stderr or stdout}")

    # 4. 跳转无障碍设置页引导用户
    _run_adb("shell", "am", "start", "-a", "android.settings.ACCESSIBILITY_SETTINGS",
             serial=serial, timeout=5)

    return ok(
        "agent install",
        data={
            "version": ver,
            "apk_size_mb": round(size_mb, 1),
            "cached_apk": cached_apk,
            "installed": True,
            "message": (
                f"Ad-CLI Agent v{ver} 安装成功。\n"
                "请在手机上完成无障碍服务授权：\n"
                "  系统设置 → 无障碍 → Ad-CLI Agent → 开启\n"
                "授权后执行 ad-cli agent setup 确认服务就绪"
            ),
            "next_step": "ad-cli agent setup",
        },
    )


def cmd_agent_setup(
    serial: str | None = None,
    port: int = DEFAULT_PORT,
    timeout: int = 60,
) -> dict:
    """执行端口转发，等待 Agent HTTP Server 就绪，输出设备信息。"""
    from core.agent_client import AgentClient, AgentError

    # 端口转发
    rc, _, stderr = _run_adb("forward", f"tcp:{port}", f"tcp:{port}", serial=serial, timeout=5)
    if rc != 0:
        return error(
            "agent setup",
            "ADB_FORWARD_FAILED",
            f"adb forward 失败: {stderr}。请确认设备已通过 USB 连接。",
        )

    client = AgentClient(port=port, serial=serial)

    # 先检查是否已就绪
    if client.is_ready():
        try:
            info = client.get_device()
            return ok(
                "agent setup",
                data={
                    "ready": True,
                    "port": port,
                    "brand": info.get("brand", ""),
                    "model": info.get("model", ""),
                    "resolution": f"{info.get('displayWidth', '')}x{info.get('displayHeight', '')}",
                    "sdk_version": info.get("sdkVersion"),
                    "package": info.get("package", ""),
                    "message": (
                        f"Agent ready: {info.get('brand', '')} {info.get('model', '')} "
                        f"({info.get('displayWidth', '')}x{info.get('displayHeight', '')})"
                    ),
                },
            )
        except AgentError:
            pass

    # 尝试广播启动 + 等待就绪
    client.try_start_via_broadcast()
    ready = _wait_for_ready(port, serial, timeout)

    if not ready:
        return error(
            "agent setup",
            "AGENT_NOT_READY",
            (
                "Agent HTTP Server 未就绪。请确认：\n"
                "  1. 已安装 Agent App：ad-cli agent install\n"
                "  2. 已在系统设置中开启 Ad-CLI Agent 无障碍服务\n"
                "  3. 设备通过 USB 连接"
            ),
            hint="adb shell am start -a android.settings.ACCESSIBILITY_SETTINGS",
        )

    try:
        info = client.get_device()
        return ok(
            "agent setup",
            data={
                "ready": True,
                "port": port,
                "brand": info.get("brand", ""),
                "model": info.get("model", ""),
                "resolution": f"{info.get('displayWidth', '')}x{info.get('displayHeight', '')}",
                "sdk_version": info.get("sdkVersion"),
                "package": info.get("package", ""),
                "message": (
                    f"Agent ready: {info.get('brand', '')} {info.get('model', '')} "
                    f"({info.get('displayWidth', '')}x{info.get('displayHeight', '')})"
                ),
            },
        )
    except AgentError as e:
        return error("agent setup", "AGENT_ERROR", str(e))


def cmd_agent_status(
    serial: str | None = None,
    port: int = DEFAULT_PORT,
) -> dict:
    """查询 Agent 运行状态：端口转发 + HTTP /device + ADB 广播状态。"""
    from core.agent_client import AgentClient, AgentError

    # 1. 端口转发状态
    rc, _, _ = _run_adb("forward", f"tcp:{port}", f"tcp:{port}", serial=serial, timeout=5)
    forward_ok = rc == 0

    client = AgentClient(port=port, serial=serial)

    # 2. HTTP 服务状态
    http_ok = False
    device_info: dict = {}
    try:
        device_info = client.get_device()
        http_ok = bool(device_info.get("serviceRunning"))
    except AgentError:
        pass

    # 3. ADB 广播读取状态文件
    broadcast_status: dict = {}
    rc2, stdout2, _ = _run_adb(
        "shell", "cat",
        f"/sdcard/Android/data/{AGENT_PACKAGE}/files/status.json",
        serial=serial, timeout=5,
    )
    if rc2 == 0 and stdout2:
        try:
            broadcast_status = json.loads(stdout2)
        except Exception:
            pass

    return ok(
        "agent status",
        data={
            "forward_ready": forward_ok,
            "http_server_ready": http_ok,
            "port": port,
            "service_running": device_info.get("serviceRunning", broadcast_status.get("httpServer", False)),
            "accessibility_enabled": broadcast_status.get("accessibility", device_info.get("accessibility", False)),
            "package": device_info.get("package", ""),
            "brand": device_info.get("brand", ""),
            "model": device_info.get("model", ""),
            "resolution": (
                f"{device_info.get('displayWidth', '')}x{device_info.get('displayHeight', '')}"
                if device_info.get("displayWidth") else ""
            ),
            "sdk_version": device_info.get("sdkVersion", broadcast_status.get("sdkVersion")),
            "agent_package": AGENT_PACKAGE,
        },
    )


def cmd_agent_diagnose(
    serial: str | None = None,
    port: int = DEFAULT_PORT,
) -> dict:
    """一键排查 Agent 未就绪的原因，逐项检查并给出修复建议。"""
    from core.agent_client import AgentClient, AgentError

    checks: list[dict] = []
    all_ok = True

    # ── 1. ADB 连接 ──────────────────────────────────────────
    rc_adb, stdout_adb, stderr_adb = _run_adb("devices", serial=serial, timeout=5)
    if rc_adb != 0:
        all_ok = False
        checks.append({
            "item": "ADB 可用",
            "status": "fail",
            "detail": f"adb 命令不可用: {stderr_adb}",
            "fix": "请安装 Android SDK Platform Tools 并确保 adb 在 PATH 中",
        })
    else:
        devices = [l for l in stdout_adb.split("\n") if l.strip() and "List of devices" not in l]
        if not devices:
            all_ok = False
            checks.append({
                "item": "设备连接",
                "status": "fail",
                "detail": "未检测到已连接的设备",
                "fix": "请通过 USB 连接 Android 设备，并确保已开启「开发者选项 → USB 调试」",
            })
        else:
            checks.append({
                "item": "设备连接",
                "status": "ok",
                "detail": f"已连接 {len(devices)} 台设备",
            })

    # ── 2. APK 是否已安装 ────────────────────────────────────
    rc_pkg, stdout_pkg, _ = _run_adb("shell", "pm", "list", "packages", AGENT_PACKAGE,
                                      serial=serial, timeout=10)
    pkg_installed = rc_pkg == 0 and AGENT_PACKAGE in stdout_pkg
    if not pkg_installed:
        all_ok = False
        checks.append({
            "item": "Agent APK 安装",
            "status": "fail",
            "detail": f"未找到包 {AGENT_PACKAGE}",
            "fix": "请执行 ad-cli agent install 下载并安装 Agent APK",
        })
    else:
        checks.append({
            "item": "Agent APK 安装",
            "status": "ok",
            "detail": f"{AGENT_PACKAGE} 已安装",
        })

    # ── 3. 无障碍服务 ────────────────────────────────────────
    rc_acc, stdout_acc, _ = _run_adb(
        "shell", "settings", "get", "secure", "enabled_accessibility_services",
        serial=serial, timeout=5,
    )
    acc_enabled = rc_acc == 0 and AGENT_PACKAGE in stdout_acc
    if not acc_enabled:
        all_ok = False
        checks.append({
            "item": "无障碍服务",
            "status": "fail",
            "detail": "Ad-CLI Agent 无障碍服务未开启",
            "fix": (
                "请在手机上操作：\n"
                "  系统设置 → 无障碍 → Ad-CLI Agent → 开启\n"
                "或执行 adb shell am start -a android.settings.ACCESSIBILITY_SETTINGS 打开设置页"
            ),
        })
    else:
        checks.append({
            "item": "无障碍服务",
            "status": "ok",
            "detail": "Ad-CLI Agent 无障碍服务已开启",
        })

    # ── 4. 端口转发 ──────────────────────────────────────────
    rc_fwd, _, stderr_fwd = _run_adb("forward", f"tcp:{port}", f"tcp:{port}",
                                      serial=serial, timeout=5)
    fwd_ok = rc_fwd == 0
    if not fwd_ok:
        all_ok = False
        checks.append({
            "item": "端口转发",
            "status": "fail",
            "detail": f"adb forward tcp:{port} 失败: {stderr_fwd}",
            "fix": "请确认设备已通过 USB 连接且未被其他程序占用该端口",
        })
    else:
        checks.append({
            "item": "端口转发",
            "status": "ok",
            "detail": f"tcp:{port} 已转发到设备",
        })

    # ── 5. HTTP 服务就绪 ─────────────────────────────────────
    client = AgentClient(port=port, serial=serial)
    http_ok = client.is_ready()
    if not http_ok:
        # 尝试广播启动再试
        client.try_start_via_broadcast()
        time.sleep(3)
        http_ok = client.is_ready()

    if not http_ok:
        all_ok = False
        # 诊断具体原因
        reason_parts = []
        if not acc_enabled:
            reason_parts.append("无障碍服务未开启")
        if not fwd_ok:
            reason_parts.append("端口转发失败")
        reason = "；".join(reason_parts) if reason_parts else "未知原因（可能 App 未在前台运行）"

        fix_steps = []
        if not acc_enabled:
            fix_steps.append(
                "1. 开启无障碍服务：系统设置 → 无障碍 → Ad-CLI Agent → 开启"
            )
        if acc_enabled and fwd_ok:
            fix_steps.append(
                "1. 尝试手动打开 Agent App（执行 adb shell monkey -p {0} 1）".format(AGENT_PACKAGE)
            )
            fix_steps.append("2. 等待 5 秒后执行 ad-cli agent setup")
        if not fix_steps:
            fix_steps.append("1. 执行 ad-cli agent install 安装 Agent")
            fix_steps.append("2. 开启无障碍服务")
            fix_steps.append("3. 执行 ad-cli agent setup 确认就绪")

        checks.append({
            "item": "HTTP 服务",
            "status": "fail",
            "detail": f"端口 {port} 无响应 ({reason})",
            "fix": "\n".join(fix_steps),
        })
    else:
        checks.append({
            "item": "HTTP 服务",
            "status": "ok",
            "detail": f"http://localhost:{port} 就绪",
        })

    # ── 汇总 ──────────────────────────────────────────────────
    passed = sum(1 for c in checks if c["status"] == "ok")
    total = len(checks)
    summary = "所有检查通过 ✅" if all_ok else f"{passed}/{total} 项通过，请按修复建议操作"

    return ok(
        "agent diagnose",
        data={
            "all_ok": all_ok,
            "passed": passed,
            "total": total,
            "summary": summary,
            "checks": checks,
            "next_step": (
                "ad-cli agent setup"
                if all_ok
                else checks[-1]["fix"].split("\n")[0] if checks else ""
            ),
        },
    )
