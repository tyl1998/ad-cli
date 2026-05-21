#!/usr/bin/env python3
"""ad-cli thin router - delegates to commands.*"""

import argparse, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adb_client import ADBClient, ADBError
from output import ok, error, exit_with, err_disconnected, ReportError
from commands.perception import cmd_dump, cmd_find, cmd_screenshot, cmd_exists, cmd_get_text, cmd_wait
from commands.action import cmd_tap, cmd_input, cmd_scroll, cmd_back, cmd_keyevent
from commands.app import cmd_app_list, cmd_app_info, cmd_app_launch, cmd_app_stop, cmd_app_install
from commands.system import cmd_device_info, cmd_page_info
from commands.report_cmd import (
    cmd_report_start, cmd_report_status, cmd_report_case_start,
    cmd_report_case_end, cmd_report_finalize, cmd_report_note,
    cmd_report_serve, cmd_report_serve_stop, _resolve_report_dir, maybe_record_execution,
)


def get_adb(serial=None) -> ADBClient:
    adb = ADBClient(serial)
    if not adb.is_connected():
        exit_with(err_disconnected("init"))
    return adb


def _mirror_pid_file() -> str:
    return os.path.join(os.path.expanduser("~"), ".ad-cli", "mirror_server.pid")


def _cmd_replay(args) -> dict:
    # 仅在用户明确传入 --mirror 时才后台启动投屏（web 模式）
    if getattr(args, "mirror", False):
        import subprocess as _sp
        _src_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(_src_dir)
        _venv_py = os.path.join(_project_root, ".venv", "bin", "python3")
        if os.path.exists(_venv_py):
            _mirror_proc = _sp.Popen(
                [_venv_py, os.path.join(_src_dir, "subsystems", "mirror", "scrcpy_server.py"),
                 "--mode", "web", "--port", "8889"],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            )
            # 记录 PID，供 mirror stop 使用
            os.makedirs(os.path.dirname(_mirror_pid_file()), exist_ok=True)
            with open(_mirror_pid_file(), "w") as _f:
                _f.write(f"{_mirror_proc.pid}:8889")
    if getattr(args, "recording", False):
        from replay import replay_recording
        return replay_recording(args.name,
                                speed_factor=getattr(args, "speed_factor", 1.0),
                                dry_run=getattr(args, "dry_run", False))
    from replay import replay_report
    return replay_report(
        report_dir=_resolve_report_dir(getattr(args, "name", None)),
        full=getattr(args, "full", False),
        case_id=getattr(args, "case_id", None),
        generate_report=getattr(args, "generate_report", False),
        speed_factor=getattr(args, "speed_factor", 1.0),
        dry_run=getattr(args, "dry_run", False),
    )


def _cmd_cache(args) -> dict:
    from cache import store as _cs, config as _cc
    if args.action == "stats":
        return ok("cache stats", data=_cs.stats())
    if args.action == "clear":
        pkg = getattr(args, "package", None)
        return ok("cache clear", data={"deleted": _cs.clear(pkg), "package": pkg})
    if args.action == "set-confidence":
        if not getattr(args, "value", None):
            return error("cache", "INVALID_ARGUMENT", "set-confidence needs a value")
        val = int(args.value)
        _cc.set_value("cache.confidence_threshold", val)
        return ok("cache set-confidence", data={"confidence_threshold": val})
    return error("cache", "UNKNOWN_ACTION", f"unknown: {args.action}")


def _cmd_mirror_stop() -> dict:
    """停止后台投屏服务（通过 PID 文件）。"""
    import signal
    pf = _mirror_pid_file()
    if not os.path.exists(pf):
        return error("mirror stop", "NOT_RUNNING", "未找到运行中的投屏服务（无 PID 文件）")
    with open(pf) as f:
        content = f.read().strip()
    try:
        pid_str, port_str = content.split(":")
        pid, port = int(pid_str), int(port_str)
    except Exception:
        os.remove(pf)
        return error("mirror stop", "BAD_PID_FILE", f"PID 文件格式错误: {content}")
    try:
        os.kill(pid, signal.SIGTERM)
        os.remove(pf)
        return ok("mirror stop", data={"pid": pid, "port": port, "message": f"已停止投屏服务 (pid={pid}, port={port})"})
    except ProcessLookupError:
        os.remove(pf)
        return ok("mirror stop", data={"pid": pid, "port": port, "message": f"进程 {pid} 已不存在，清理 PID 文件"})
    except Exception as e:
        return error("mirror stop", "KILL_FAILED", str(e))


def _cmd_mirror(args) -> None:
    import subprocess as _sp
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        scrcpy_python = sys.executable
    else:
        scrcpy_python = os.path.join(project_root, ".venv", "bin", "python3")
    scrcpy_server = os.path.join(src_dir, "subsystems", "mirror", "scrcpy_server.py")
    if not os.path.isfile(scrcpy_python):
        exit_with(error("mirror", "VENV_NOT_FOUND", ".venv not found"))
        return
    serial = getattr(args, "serial", None)
    cmd = [scrcpy_python, scrcpy_server]
    if serial:
        cmd += ["--serial", serial]
    cmd += [
        "--max-size", str(getattr(args, "max_size", 1024)),
        "--max-fps",  str(getattr(args, "max_fps", 60)),
        "--bitrate",  str(getattr(args, "bitrate", 2_000_000)),
        "--mode",     getattr(args, "mode", "window"),
        "--port",     str(getattr(args, "port", 8888)),
    ]
    if getattr(args, "sharpen", False):
        cmd.append("--sharpen")
    if getattr(args, "record", None):
        cmd += ["--record", args.record]
    try:
        proc = _sp.run(cmd)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        sys.exit(0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ad-cli",
        description=(
            "Android 自动化 CLI — ADB 感知 / 操作 / 报告 / 投屏\n\n"
            "常用示例:\n"
            "  ad-cli device info              查看连接设备信息\n"
            "  ad-cli app launch <package>     启动 App\n"
            "  ad-cli dump --screenshot        获取 UI 元素（附截图）\n"
            "  ad-cli tap --text '登录'        点击文字元素\n"
            "  ad-cli report start '回归测试'  开启测试报告\n"
            "  ad-cli mirror                   实时投屏（PySide6 窗口）\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--serial", "-s", metavar="SERIAL", help="指定设备序列号（多设备时使用）")
    sub = p.add_subparsers(dest="group", required=True, metavar="<command>")

    # ── 系统感知 ──────────────────────────────────────────────
    dev = sub.add_parser("device", help="设备信息")
    dev.add_argument("action", choices=["info"], help="info: 获取设备型号/分辨率/系统版本")

    pg = sub.add_parser("page", help="获取当前 App 页面信息（包名 / Activity）")
    pg.add_argument("action", choices=["info"])

    # ── App 管理 ──────────────────────────────────────────────
    app = sub.add_parser("app", help="App 管理：list / info / launch / stop / install")
    app.add_argument("action", choices=["list", "info", "launch", "stop", "install"],
                     help="list=列出所有 App  info/launch/stop/install=需要 <package>")
    app.add_argument("target", nargs="?", metavar="package",
                     help="App 包名，例如 com.example.app")

    # ── 报告 ──────────────────────────────────────────────────
    rpt = sub.add_parser("report", help="测试报告生命周期管理",
                         formatter_class=argparse.RawDescriptionHelpFormatter,
                         description=(
                             "测试报告子命令:\n"
                             "  start <suite>      开启报告\n"
                             "  status             查看当前激活报告状态\n"
                             "  case-start <name>  开启 case\n"
                             "  case-end           结束 case（--status passed|failed|skipped）\n"
                             "  case-pass/fail/skip  快捷结束命令\n"
                             "  note <title>       写入 AI 观察备注\n"
                             "  finalize           收口报告\n"
                             "  serve [run-dir]    启动本地预览服务\n"
                             "  stop               停止预览服务\n"
                         ))
    rpt.add_argument("action", choices=[
        "start", "status", "case-start", "case-end",
        "case-pass", "case-fail", "case-skip", "note", "finalize", "serve", "stop"],
        metavar="action")
    rpt.add_argument("name", nargs="?", metavar="name",
                     help="报告名称 / suite 名称 / case 名称 / note 标题")
    rpt.add_argument("--output-dir", metavar="DIR", help="报告输出目录（默认 ./report/）")
    rpt.add_argument("--description", metavar="TEXT", help="case 描述")
    rpt.add_argument("--content", metavar="TEXT", help="note 正文")
    rpt.add_argument("--level", default="info", choices=["info", "warning", "error"],
                     help="note 级别（默认 info）")
    rpt.add_argument("--screenshot", action="store_true", help="note 附带截图")
    rpt.add_argument("--status", default="passed", choices=["passed", "failed", "skipped"],
                     help="case-end 结果（默认 passed）")
    rpt.add_argument("--summary", metavar="TEXT", help="case 结果摘要")
    rpt.add_argument("--force", action="store_true", help="finalize 强制收口（忽略未结束 case）")
    rpt.add_argument("--port", type=int, default=8765, help="serve 监听端口（默认 8765）")

    # ── 页面感知 ──────────────────────────────────────────────
    dp = sub.add_parser("dump", help="获取当前页面 UI 元素（compact 模式）")
    dp.add_argument("--screenshot", action="store_true", help="同时截图")

    f = sub.add_parser("find", help="按 id/text/class 查找元素")
    f.add_argument("query", help="查询词（id / text / class name）")

    ss = sub.add_parser("screenshot", help="截图保存到 ./screenshot/")
    ss.add_argument("path", nargs="?", metavar="PATH", help="自定义保存路径（可选）")

    ex = sub.add_parser("exists", help="判断元素是否存在，返回 true/false")
    ex.add_argument("query", help="查询词")

    gt = sub.add_parser("get-text", help="获取元素文本内容")
    gt.add_argument("query", help="查询词")

    wt = sub.add_parser("wait", help="等待元素出现（默认超时 5000ms）")
    wt.add_argument("query", help="查询词")
    wt.add_argument("--timeout", type=int, default=5000, metavar="MS",
                    help="超时毫秒数（默认 5000）")

    # ── 操作 ──────────────────────────────────────────────────
    tap = sub.add_parser("tap", help="点击元素（--id / --text / --xy）")
    tap.add_argument("--id", metavar="ID", help="按资源 ID 定位")
    tap.add_argument("--text", metavar="TEXT", help="按文字定位")
    tap.add_argument("--xy", nargs=2, metavar=("X", "Y"), help="按坐标点击")
    tap.add_argument("--label", metavar="LABEL", help="语义标签（配合 pHash 缓存）")
    tap.add_argument("--reason", metavar="TEXT", help="点击原因（写入报告）")

    inp = sub.add_parser("input", help="在输入框输入文字")
    inp.add_argument("--id", metavar="ID", help="按资源 ID 定位输入框")
    inp.add_argument("--text", metavar="TEXT", help="按文字定位输入框")
    inp.add_argument("--value", required=True, metavar="VALUE", help="要输入的文字")

    sc = sub.add_parser("scroll", help="滑动页面")
    sc.add_argument("--direction", required=True, choices=["up", "down", "left", "right"],
                    help="滑动方向")

    sub.add_parser("back", help="模拟返回键")

    ke = sub.add_parser("keyevent", help="发送系统按键（home/back/enter/del/menu 等）")
    ke.add_argument("key", help="按键名称，例如 home / back / enter")

    # ── 投屏 ──────────────────────────────────────────────────
    mir = sub.add_parser("mirror", help="实时投屏 Android 设备",
                         formatter_class=argparse.RawDescriptionHelpFormatter,
                         description=(
                             "实时投屏示例:\n"
                             "  ad-cli mirror                        PySide6 本地窗口\n"
                             "  ad-cli mirror --mode web             浏览器 MJPEG 流\n"
                             "  ad-cli mirror --max-fps 30 --sharpen 30fps + 锐化\n"
                             "  ad-cli mirror stop                   停止后台投屏\n"
                         ))
    mir.add_argument("action", nargs="?", choices=["stop"], default=None,
                     metavar="[stop]", help="stop: 停止后台投屏服务")
    mir.add_argument("--max-size", type=int, default=1024, metavar="PX",
                     help="最大分辨率长边（默认 1024）")
    mir.add_argument("--max-fps",  type=int, default=60, metavar="FPS",
                     help="最大帧率（默认 60）")
    mir.add_argument("--bitrate",  type=int, default=2_000_000, metavar="BPS",
                     help="视频码率 bps（默认 2000000）")
    mir.add_argument("--mode", choices=["window", "web"], default="window",
                     help="展示模式：window=PySide6窗口  web=浏览器MJPEG（默认 window）")
    mir.add_argument("--port", type=int, default=8888,
                     help="web 模式监听端口（默认 8888）")
    mir.add_argument("--sharpen", action="store_true", default=False,
                     help="开启画面锐化滤镜（window 模式有效）")
    mir.add_argument("--record", default=None, metavar="NAME",
                     help="录制操作并保存为 <NAME>.json")

    # ── 回放 ──────────────────────────────────────────────────
    rp = sub.add_parser("replay", help="回放测试报告或录制文件")
    rp.add_argument("name", nargs="?", metavar="name",
                    help="报告目录名或录制文件名（省略则用最新报告）")
    rp.add_argument("--recording", action="store_true", help="回放录制文件而非报告")
    rp.add_argument("--full", action="store_true", help="回放所有 case（含已跳过）")
    rp.add_argument("--case", dest="case_id", metavar="CASE_ID", help="只回放指定 case")
    rp.add_argument("--generate-report", action="store_true", help="回放结束后生成新报告")
    rp.add_argument("--speed", type=float, default=1.0, dest="speed_factor",
                    help="回放速度倍率（默认 1.0）")
    rp.add_argument("--dry-run", action="store_true", help="空跑模式，不实际执行操作")
    rp.add_argument("--mirror", action="store_true",
                    help="回放时同步在后台启动 mirror web 投屏（端口 8889）")

    # ── 缓存 ──────────────────────────────────────────────────
    ca = sub.add_parser("cache", help="元素坐标缓存管理")
    ca.add_argument("action", choices=["stats", "clear", "set-confidence"],
                    help="stats=统计  clear=清除  set-confidence=设置置信度阈值")
    ca.add_argument("value", nargs="?", metavar="VALUE",
                    help="set-confidence 时的阈值数值（0-100）")
    ca.add_argument("--package", metavar="PKG", help="clear 时限定 App 包名")

    return p


def _dispatch_app(adb, args):
    return {
        "list":    lambda: cmd_app_list(adb),
        "info":    lambda: cmd_app_info(adb, args.target),
        "launch":  lambda: cmd_app_launch(adb, args.target),
        "stop":    lambda: cmd_app_stop(adb, args.target),
        "install": lambda: cmd_app_install(adb, args.target),
    }[args.action]()


def _dispatch_report(args):
    serial = getattr(args, "serial", None)
    if args.action == "start":
        if not args.name:
            return error("report start", "INVALID_ARGUMENT", "suite name required")
        return cmd_report_start(ADBClient(serial), args.name, args.output_dir)
    if args.action == "status":
        return cmd_report_status()
    if args.action == "case-start":
        if not args.name:
            return error("report case-start", "INVALID_ARGUMENT", "case name required")
        return cmd_report_case_start(args.name, args.description)
    if args.action in ("case-end", "case-pass", "case-fail", "case-skip"):
        status_map = {"case-end": args.status, "case-pass": "passed",
                      "case-fail": "failed", "case-skip": "skipped"}
        return cmd_report_case_end(status_map[args.action], args.summary)
    if args.action == "note":
        if not args.name:
            return error("report note", "INVALID_ARGUMENT", "title required")
        screenshot_path = None
        if args.screenshot:
            adb = ADBClient(serial)
            if adb.is_connected():
                from commands.perception import _take_screenshot
                screenshot_path = _take_screenshot(adb)
        return cmd_report_note(args.name, args.content, args.level, screenshot_path)
    if args.action == "finalize":
        return cmd_report_finalize(force=getattr(args, "force", False))
    if args.action == "serve":
        return cmd_report_serve(args.name, getattr(args, "port", 8765))
    if args.action == "stop":
        return cmd_report_serve_stop()
    return error("report", "UNKNOWN_COMMAND", f"unknown: {args.action}")


_ADB_COMMANDS = {
    "device":     lambda adb, args: cmd_device_info(adb),
    "page":       lambda adb, args: cmd_page_info(adb),
    "app":        lambda adb, args: _dispatch_app(adb, args),
    "dump":       lambda adb, args: cmd_dump(adb, getattr(args, "screenshot", False)),
    "find":       lambda adb, args: cmd_find(adb, args.query),
    "screenshot": lambda adb, args: cmd_screenshot(adb, getattr(args, "path", None)),
    "tap":        lambda adb, args: cmd_tap(adb, args),
    "input":      lambda adb, args: cmd_input(adb, args),
    "scroll":     lambda adb, args: cmd_scroll(adb, args.direction),
    "back":       lambda adb, args: cmd_back(adb),
    "keyevent":   lambda adb, args: cmd_keyevent(adb, args.key),
    "exists":     lambda adb, args: cmd_exists(adb, args.query),
    "get-text":   lambda adb, args: cmd_get_text(adb, args.query),
    "wait":       lambda adb, args: cmd_wait(adb, args.query, args.timeout),
}


def main():
    parser = build_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    if len(sys.argv) == 1:
        parser.print_help()
        sys.stdout.flush()
        sys.exit(0)
    args = parser.parse_args()
    started_at = time.time()
    adb = None
    try:
        if args.group == "mirror":
            if getattr(args, "action", None) == "stop":
                exit_with(_cmd_mirror_stop())
            _cmd_mirror(args)
            return
        elif args.group == "replay":
            result = _cmd_replay(args)
        elif args.group == "cache":
            result = _cmd_cache(args)
        elif args.group == "report":
            result = _dispatch_report(args)
        elif args.group in _ADB_COMMANDS:
            adb = get_adb(getattr(args, "serial", None))
            result = _ADB_COMMANDS[args.group](adb, args)
        else:
            result = error("cli", "UNKNOWN_COMMAND", f"unknown: {args.group}")
    except ADBError as e:
        result = error("cli", "ADB_ERROR", str(e))
    except ReportError as e:
        result = error("report", e.code.value, str(e))
    except Exception as e:
        result = error("cli", "RUNTIME_ERROR", str(e))

    ended_at = time.time()
    try:
        maybe_record_execution(args, result, started_at, ended_at, adb=adb)
    except Exception:
        pass
    exit_with(result)


if __name__ == "__main__":
    main()
