"""
投屏服务器入口（薄包装层）

实际实现仍在 src/scrcpy_server.py，此文件作为 subsystems 命名空间的代理，
方便未来将 scrcpy_server.py 完整迁移至此目录。

run_mirror     — PySide6 窗口模式
run_mirror_web — 浏览器 MJPEG 模式
"""
from scrcpy_server import run_mirror, run_mirror_web

__all__ = ["run_mirror", "run_mirror_web"]
