"""App 管理命令（从 app_manager 薄 re-export）"""
from app_manager import (
    cmd_app_list,
    cmd_app_info,
    cmd_app_launch,
    cmd_app_stop,
    cmd_app_install,
)

__all__ = [
    "cmd_app_list", "cmd_app_info", "cmd_app_launch",
    "cmd_app_stop", "cmd_app_install",
]
