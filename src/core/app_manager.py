"""
App 管理模块
处理 app list / info / launch / stop / install 命令
"""
import os

from adb_client import ADBClient, ADBError
from output import ok, error, err_app_not_installed, err_disconnected


def cmd_app_list(adb: ADBClient) -> dict:
    """列出所有可启动的 App（有桌面图标）"""
    apps = adb.list_launcher_apps()
    return ok("app list", data=apps, total=len(apps))


def cmd_app_info(adb: ADBClient, package: str) -> dict:
    """查询某个 App 的详细信息"""
    installed = adb.is_app_installed(package)
    if not installed:
        return err_app_not_installed("app info", package)

    version = adb.get_app_version(package)
    running = adb.is_app_running(package)
    return ok("app info", data={
        "package":   package,
        "installed": True,
        "running":   running,
        "version":   version,
    })


def cmd_app_launch(adb: ADBClient, package: str) -> dict:
    """启动 App，等待页面稳定后返回"""
    if not adb.is_app_installed(package):
        return err_app_not_installed("app launch", package)

    adb.launch_app(package)
    adb.wait_stable(timeout_ms=3000)
    page = adb.get_current_page()
    return ok("app launch", data={
        "package":  package,
        "page_after": page.get("activity", ""),
    })


def cmd_app_stop(adb: ADBClient, package: str) -> dict:
    """强制关闭 App"""
    adb.stop_app(package)
    return ok("app stop", data={"package": package})


def cmd_app_install(adb: ADBClient, apk_path: str) -> dict:
    """安装 APK"""
    if not os.path.exists(apk_path):
        return error("app install", "FILE_NOT_FOUND",
                     f"找不到文件 '{apk_path}'，请确认路径正确")
    adb.install_apk(apk_path)
    return ok("app install", data={"apk_path": apk_path, "result": "安装成功"})


def cmd_device_info(adb: ADBClient) -> dict:
    """获取设备基本信息"""
    info = adb.get_device_info()
    return ok("device info", data=info)


def cmd_page_info(adb: ADBClient) -> dict:
    """获取当前页面信息"""
    page = adb.get_current_page()
    return ok("page info", data=page)
