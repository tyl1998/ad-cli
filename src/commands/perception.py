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


def _take_screenshot_from_agent(agent_png: bytes) -> str | None:
    """将 Agent 返回的 PNG bytes 保存到 screenshot/ 目录，失败返回 None。"""
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(src_dir))
    screenshot_dir = os.path.join(project_root, "screenshot")
    os.makedirs(screenshot_dir, exist_ok=True)
    filename = f"screenshot_{datetime.now().strftime('%H%M%S_%f')}.png"
    path = os.path.join(screenshot_dir, filename)
    try:
        with open(path, "wb") as f:
            f.write(agent_png)
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


def _agent_element_to_compact(elem: dict) -> dict:
    """将 Agent /elements 返回的元素格式转换为 ad-cli compact 格式。"""
    return {
        "type":         elem.get("className", "").split(".")[-1],
        "text":         elem.get("text", "") or elem.get("contentDesc", ""),
        "id":           (elem.get("resourceId") or "").split("/")[-1],
        "resource_id":  elem.get("resourceId", ""),
        "center":       [elem.get("x", 0), elem.get("y", 0)],
        "bounds":       elem.get("bounds", ""),
        "clickable":    elem.get("clickable", False),
        "checkable":    elem.get("checkable", False),
        "checked":      elem.get("checked", False),
        "scrollable":   elem.get("scrollable", False),
        "source":       elem.get("source", "native"),
        **({"inferred_type": elem["inferredType"]} if elem.get("inferredType") else {}),
        **({"confidence": elem["confidence"]} if "confidence" in elem else {}),
        **({"has_link": elem["hasLink"]} if elem.get("hasLink") else {}),
        **({"links": elem["links"]} if elem.get("links") else {}),
    }


# ── 命令实现 ─────────────────────────────────────────────────────

def cmd_dump(
    adb: ADBClient,
    with_screenshot: bool = False,
    force_ocr: bool = False,
    agent_port: int | None = None,
) -> dict:
    """获取当前页面 UI 元素。

    优先级：
    1. 若 agent_port 已指定 → 使用 Agent HTTP API（/elements?ocr=&screenshot=）
    2. 否则 → 使用传统 uiautomator dump（XML 解析）

    Parameters
    ----------
    force_ocr:
        传递给 Agent /elements?ocr=1（仅在 agent 模式下有效）。
    agent_port:
        Agent HTTP Server 端口（不指定则走传统模式）。
    """
    # ── Agent 模式 ────────────────────────────────────────────
    if agent_port is not None:
        return _cmd_dump_agent(
            agent_port=agent_port,
            with_screenshot=with_screenshot,
            force_ocr=force_ocr,
        )

    # ── 传统 uiautomator 模式 ─────────────────────────────────
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


def _cmd_dump_agent(
    agent_port: int,
    with_screenshot: bool = False,
    force_ocr: bool = False,
) -> dict:
    """通过 Agent HTTP API 获取 UI 元素。"""
    from core.agent_client import AgentClient, AgentError

    client = AgentClient(port=agent_port)
    try:
        raw = client.get_elements(ocr=force_ocr, screenshot=with_screenshot)
    except AgentError as e:
        return error("dump", "AGENT_ERROR", str(e),
                     hint="请先执行 ad-cli agent setup 确认 Agent 服务就绪")

    if not raw.get("success"):
        return error("dump", "AGENT_ERROR", raw.get("error", "Agent 返回失败"))

    elements_raw = raw.get("elements", [])
    compact_list = [_agent_element_to_compact(e) for e in elements_raw]

    resp = ok(
        "dump",
        data=compact_list,
        mode=raw.get("captureMode", "native"),
        source="agent",
        total_elements=raw.get("count", len(elements_raw)),
        returned=len(compact_list),
        native_count=raw.get("nativeCount", 0),
        ocr_count=raw.get("ocrCount", 0),
        has_web_view=raw.get("hasWebView", False),
        package=raw.get("package", ""),
    )
    if raw.get("hint"):
        resp["hint"] = raw["hint"]

    # 处理 screenshot：Agent 返回 base64 → 写入本地文件
    if with_screenshot:
        agent_b64 = raw.get("screenshot")
        if agent_b64:
            import base64
            try:
                png_bytes = base64.b64decode(agent_b64)
                path = _take_screenshot_from_agent(png_bytes)
                if path:
                    resp["screenshot"] = path
            except Exception:
                pass

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


def cmd_screenshot(adb: ADBClient, path: str | None = None, agent_port: int | None = None) -> dict:
    """截图保存到 ./screenshot/ 目录。

    Parameters
    ----------
    agent_port:
        指定端口走 Agent HTTP API（适用于 ADB 截图不可用的设备）。
    """
    # ── Agent 模式 ────────────────────────────────────────────
    if agent_port is not None:
        from core.agent_client import AgentClient, AgentError
        client = AgentClient(port=agent_port)
        try:
            png_bytes = client.screenshot()
            if not path:
                src_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(src_dir))
                screenshot_dir = os.path.join(project_root, "screenshot")
                os.makedirs(screenshot_dir, exist_ok=True)
                path = os.path.join(screenshot_dir,
                                    f"screenshot_{datetime.now().strftime('%H%M%S_%f')}.png")
            with open(path, "wb") as f:
                f.write(png_bytes)
            return ok("screenshot", data={"path": path, "source": "agent"})
        except AgentError as e:
            return error("screenshot", "AGENT_ERROR", str(e),
                         hint="请先执行 ad-cli agent setup 确认 Agent 服务就绪")

    # ── 传统 ADB 模式 ─────────────────────────────────────────
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
