"""
统一输出格式模块
所有命令的返回值都通过此模块生成，确保格式一致
"""
import json
import sys
import sys as _sys
from enum import Enum

# Python 3.11+ 有内置 StrEnum，低版本自行兼容
if _sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Python 3.10 兼容的 StrEnum 实现"""
        def __str__(self) -> str:
            return self.value


class ErrorCode(StrEnum):
    DEVICE_DISCONNECTED    = "DEVICE_DISCONNECTED"
    ELEMENT_NOT_FOUND      = "ELEMENT_NOT_FOUND"
    AMBIGUOUS_MATCH        = "AMBIGUOUS_MATCH"
    APP_NOT_INSTALLED      = "APP_NOT_INSTALLED"
    APP_NOT_RUNNING        = "APP_NOT_RUNNING"
    TIMEOUT                = "TIMEOUT"
    PERMISSION_DENIED      = "PERMISSION_DENIED"
    FILE_NOT_FOUND         = "FILE_NOT_FOUND"
    INVALID_ARGUMENT       = "INVALID_ARGUMENT"
    INVALID_BOUNDS         = "INVALID_BOUNDS"
    INVALID_DIRECTION      = "INVALID_DIRECTION"
    REPORT_NOT_ACTIVE      = "REPORT_NOT_ACTIVE"
    REPORT_CASE_NOT_ACTIVE = "REPORT_CASE_NOT_ACTIVE"
    REPORT_FINALIZE_BLOCKED= "REPORT_FINALIZE_BLOCKED"
    ADB_ERROR              = "ADB_ERROR"
    RUNTIME_ERROR          = "RUNTIME_ERROR"
    INTERNAL_ERROR         = "INTERNAL_ERROR"
    UNKNOWN_COMMAND        = "UNKNOWN_COMMAND"


class ReportError(RuntimeError):
    """报告相关异常，携带结构化 ErrorCode 避免字符串匹配"""
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code


def ok(command: str, data=None, **kwargs) -> dict:
    """成功响应"""
    result = {"status": "ok", "command": command}
    result.update(kwargs)
    if data is not None:
        result["data"] = data
    return result


def error(command: str, code: str, message: str, **kwargs) -> dict:
    """错误响应"""
    result = {"status": "error", "command": command, "code": code, "message": message}
    result.update(kwargs)
    return result


def print_result(result: dict):
    """输出 JSON 结果到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def exit_with(result: dict):
    """输出结果并退出，error 时退出码为 1"""
    print_result(result)
    sys.exit(0 if result["status"] == "ok" else 1)


# ── 常用错误快捷方法 ──────────────────────────────────────────

def err_disconnected(command: str):
    return error(command, "DEVICE_DISCONNECTED", "设备未连接，请检查 USB 连接或 adb devices")


def err_not_found(command: str, query: str):
    return error(command, "ELEMENT_NOT_FOUND",
                 f"找不到元素 '{query}'，建议先调用 dump 确认当前页面元素")


def err_ambiguous(command: str, query: str, count: int):
    return error(command, "AMBIGUOUS_MATCH",
                 f"找到 {count} 个匹配 '{query}' 的元素，请提供更精确的条件")


def err_app_not_installed(command: str, package: str):
    return error(command, "APP_NOT_INSTALLED",
                 f"未找到 {package}，该 App 可能未安装",
                 hint="可调用 app install <apk_path> 进行安装")


def err_timeout(command: str, query: str, timeout_ms: int):
    return error(command, "TIMEOUT",
                 f"等待元素 '{query}' 超时（{timeout_ms}ms），页面可能未正确跳转")


def err_permission(command: str):
    return error(command, "PERMISSION_DENIED",
                 "ADB 权限不足，请确认手机已开启 USB 调试并授权")


def err_report_not_active(command: str):
    return error(command, "REPORT_NOT_ACTIVE", "当前没有激活中的报告，请先执行 report start")
