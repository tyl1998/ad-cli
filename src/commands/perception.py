"""感知类命令：dump, find, screenshot, exists, get-text, wait

公共工具函数 _take_screenshot / _parse_resolution 也在此处定义，
供 commands.action 和 commands.report_cmd 导入使用。
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime

from adb_client import ADBClient
from ui_parser import parse_xml, compact, find_exact, find_fuzzy
from output import ok, error, err_not_found, err_timeout


# ── 共享工具（供 action / report_cmd 导入）───────────────────────

def _take_screenshot(adb: ADBClient) -> str | None:
    """截图保存到项目根 screenshot/ 目录，失败返回 None。"""
    src_dir = os.path.dirname(os.path.abspath(__file__))       # commands/
    project_root = os.path.dirname(os.path.dirname(src_dir))   # ad-cli/
    screenshot_dir = os.path.join(project_root, "screenshot")
    os.makedirs(screenshot_dir, exist_ok=True)
    filename = f"screenshot_{datetime.now().strftime('%H%M%S_%f')}.png"
    path = os.path.join(screenshot_dir, filename)
    try:
        adb.screenshot(path)
        return path
    except Exception:
        return None


def _parse_resolution(resolution: str | None) -> dict | None:
    if not resolution:
        return None
    m = re.search(r"(\d+)x(\d+)", resolution)
    if not m:
        return None
    return {"width": int(m.group(1)), "height": int(m.group(2))}


# ── 命令实现 ─────────────────────────────────────────────────────

def cmd_dump(adb: ADBClient, with_screenshot: bool = False) -> dict:
    xml = adb.dump_ui()
    elements = parse_xml(xml)
    result = compact(elements)

    if len(result) == 0:
        screenshot_path = _take_screenshot(adb)
        resp = ok("dump",
                  data=elements,
                  mode="full",
                  reason="compact 模式返回 0 个元素，已自动切换全量",
                  total_elements=len(elements),
                  returned=len(elements))
        if screenshot_path:
            resp["screenshot"] = screenshot_path
            resp["hint"] = "已自动截图，可结合图片辅助判断页面内容"
        return resp

    resp = ok("dump",
              data=result,
              mode="compact",
              total_elements=len(elements),
              returned=len(result))
    if with_screenshot:
        screenshot_path = _take_screenshot(adb)
        if screenshot_path:
            resp["screenshot"] = screenshot_path
    return resp


def cmd_find(adb: ADBClient, query: str) -> dict:
    xml = adb.dump_ui()
    elements = parse_xml(xml)
    exact = find_exact(elements, query)

    if len(exact) == 1:
        e = exact[0]
        return ok("find", matched="exact", data={
            "type":      e["type"],
            "text":      e["text"],
            "id":        e["id"],
            "center":    e["center"],
            "bounds":    e["bounds"],
            "clickable": e["clickable"],
        })

    if len(exact) > 1:
        return error("find", "AMBIGUOUS_MATCH",
                     f"找到 {len(exact)} 个精确匹配 '{query}'",
                     matched="exact_multiple",
                     candidates=[{
                         "type": e["type"], "text": e["text"],
                         "id": e["id"], "center": e["center"],
                     } for e in exact])

    candidates = find_fuzzy(elements, query)
    if candidates:
        return ok("find",
                  matched="fuzzy",
                  message=f"未找到精确匹配 '{query}'，以下是相似结果，请 AI 判断是否符合预期",
                  candidates=candidates)

    return err_not_found("find", query)


def cmd_screenshot(adb: ADBClient, path: str | None = None) -> dict:
    if not path:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(src_dir))
        screenshot_dir = os.path.join(project_root, "screenshot")
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir,
                            f"screenshot_{datetime.now().strftime('%H%M%S_%f')}.png")
    adb.screenshot(path)
    return ok("screenshot", data={"path": path})


def cmd_exists(adb: ADBClient, query: str) -> dict:
    xml = adb.dump_ui()
    elements = parse_xml(xml)
    exact = find_exact(elements, query)
    return ok("exists", data={"query": query, "exists": len(exact) > 0})


def cmd_get_text(adb: ADBClient, query: str) -> dict:
    xml = adb.dump_ui()
    elements = parse_xml(xml)
    exact = find_exact(elements, query)
    if not exact:
        return err_not_found("get-text", query)
    return ok("get-text", data={"query": query, "text": exact[0]["text"]})


def cmd_wait(adb: ADBClient, query: str, timeout_ms: int = 5000) -> dict:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        xml = adb.dump_ui()
        elements = parse_xml(xml)
        exact = find_exact(elements, query)
        if exact:
            e = exact[0]
            return ok("wait", data={
                "query":  query,
                "found":  True,
                "text":   e["text"],
                "id":     e["id"],
                "center": e["center"],
            })
        time.sleep(0.5)
    return err_timeout("wait", query, timeout_ms)
