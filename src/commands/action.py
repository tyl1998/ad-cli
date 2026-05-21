"""操作类命令：tap, input, scroll, back, keyevent

包含：
  - _APP_VERSION_CACHE / _get_app_version_cached（懒加载，进程级）
  - _capture_action_evidence（截图 + 坐标打包）
  - _resolve_element（按 id/text dump 找元素）
  - cmd_tap / cmd_input / cmd_scroll / cmd_back / cmd_keyevent
"""
from __future__ import annotations

import re
import time

from adb_client import ADBClient
from ui_parser import parse_xml, find_exact
from output import ok, error, err_not_found
from commands.perception import _take_screenshot, _parse_resolution

# ── App 版本懒加载缓存（进程级，按需查询一次）────────────────────
_APP_VERSION_CACHE: dict[str, str] = {}


def _get_app_version_cached(adb: ADBClient, package: str) -> str:
    """同一进程内只查询一次 app_version，后续复用内存值。"""
    if package not in _APP_VERSION_CACHE:
        try:
            _APP_VERSION_CACHE[package] = adb.get_app_version(package)
        except Exception:
            _APP_VERSION_CACHE[package] = ""
    return _APP_VERSION_CACHE[package]


def _capture_action_evidence(
    adb: ADBClient,
    *,
    x: int,
    y: int,
    action: str,
    bounds: str | None = None,
    target_id: str | None = None,
    target_text: str | None = None,
) -> dict:
    screenshot_path = _take_screenshot(adb)
    viewport = None
    try:
        viewport = _parse_resolution(adb.get_device_info().get("resolution"))
    except Exception:
        pass

    spotlight = {
        "action": action, "x": x, "y": y,
        "bounds": bounds, "target_id": target_id, "target_text": target_text,
    }
    if viewport:
        spotlight["viewport"] = viewport
    return {"screenshot": screenshot_path, "spotlight": spotlight}


def _resolve_element(adb: ADBClient, id_val=None, text_val=None) -> dict | None:
    xml = adb.dump_ui()
    elements = parse_xml(xml)
    query = id_val or text_val
    exact = find_exact(elements, query)
    return exact[0] if len(exact) == 1 else None


# ── cmd_tap ──────────────────────────────────────────────────────

def cmd_tap(adb: ADBClient, args) -> dict:
    try:
        page_before = adb.get_current_page()
    except Exception:
        page_before = {}

    pkg = page_before.get("package", "")
    act = page_before.get("activity", "")

    # ── 模式 1：--xy（坐标点击，可附带 --label 写入 pHash 缓存）────
    if args.xy:
        x, y = int(args.xy[0]), int(args.xy[1])
        evidence = _capture_action_evidence(adb, x=x, y=y, action="tap")
        adb.tap(x, y)
        adb.wait_stable()
        page = adb.get_current_page()

        label = getattr(args, "label", None)
        if label and evidence.get("screenshot") and pkg and act:
            try:
                from cache import store as _cs, config as _cc, phash as _ph
                if _cc.get("cache.enabled", True):
                    app_ver = _get_app_version_cached(adb, pkg)
                    page_hash = _ph.compute(evidence["screenshot"])
                    _cs.upsert_label(pkg, act, app_ver, label, x, y,
                                     page_hash, source_exec=evidence.get("screenshot"))
            except Exception:
                pass

        return ok("tap",
                  target={"xy": [x, y], **({"label": label} if label else {})},
                  screenshot=evidence.get("screenshot"),
                  spotlight=evidence.get("spotlight"),
                  interaction={
                      "kind": "coordinate",
                      "selector": {"xy": [x, y]},
                      "reason": getattr(args, "reason", None),
                      "fallback": False,
                  },
                  page_before=page_before,
                  page_after=page,
                  page_after_activity=page.get("activity", ""))

    # ── 模式 2：--label 纯缓存（无 --xy / --id / --text）────────────
    label = getattr(args, "label", None)
    if label and not args.id and not args.text:
        if not pkg or not act:
            return error("tap", "PAGE_UNKNOWN", "无法获取当前页面信息，缓存查找失败")
        try:
            from cache import store as _cs, config as _cc, phash as _ph
            if not _cc.get("cache.enabled", True):
                return error("tap", "CACHE_DISABLED", "缓存已关闭，--label 模式需要缓存启用")
            screenshot_path = _take_screenshot(adb)
            if not screenshot_path:
                return error("tap", "SCREENSHOT_FAILED", "截图失败，无法计算页面指纹")
            page_hash = _ph.compute(screenshot_path)
            app_ver = _get_app_version_cached(adb, pkg)
            cached_pos = _cs.lookup_label(
                pkg, act, app_ver, label, page_hash,
                _cc.get("cache.confidence_threshold", 1),
                _cc.get("cache.ttl_days", 7),
                _cc.get("cache.hamming_threshold", 10),
            )
        except Exception as e:
            return error("tap", "CACHE_ERROR", f"缓存查找异常: {e}")

        if not cached_pos:
            return error("tap", "CACHE_MISS",
                         f"标签 '{label}' 在当前页面无缓存，请先用 --xy x y --label '{label}' 执行一次写入",
                         label=label,
                         hint="用 tap --xy <x> <y> --label <label> 执行一次后缓存自动建立")

        x, y = cached_pos["center_x"], cached_pos["center_y"]
        evidence_label = _capture_action_evidence(adb, x=x, y=y, action="tap",
                                                   bounds=cached_pos.get("bounds"))
        t0 = time.time()
        adb.tap(x, y)
        adb.wait_stable()
        waited_ms = int((time.time() - t0) * 1000)
        page = adb.get_current_page()
        try:
            _cs.upsert_label(pkg, act, app_ver, label, x, y, page_hash,
                             cached_pos.get("bounds"))
        except Exception:
            pass
        return ok("tap",
                  target={"label": label, "center": [x, y],
                          "cache_hit": True,
                          "hamming_dist": cached_pos.get("hamming_dist")},
                  screenshot=evidence_label.get("screenshot"),
                  spotlight=evidence_label.get("spotlight"),
                  interaction={
                      "kind": "label-cache",
                      "selector": {"label": label},
                      "reason": getattr(args, "reason", None),
                      "fallback": False,
                  },
                  page_before=page_before,
                  page_after=page,
                  waited_ms=waited_ms,
                  page_after_activity=page.get("activity", ""))

    # ── 模式 3：--id / --text（dump 找元素，带结构化缓存）───────────
    query = args.id or args.text
    query_type = "id" if args.id else "text"

    cached_pos = None
    if pkg and act:
        try:
            from cache import store as _cs, config as _cc
            if _cc.get("cache.enabled", True):
                app_ver = _get_app_version_cached(adb, pkg)
                cached_pos = _cs.lookup(
                    pkg, act, app_ver, query, query_type,
                    _cc.get("cache.confidence_threshold", 1),
                    _cc.get("cache.ttl_days", 7),
                )
        except Exception:
            cached_pos = None

    if cached_pos:
        x, y = cached_pos["center_x"], cached_pos["center_y"]
        evidence = _capture_action_evidence(adb, x=x, y=y, action="tap",
                                            bounds=cached_pos.get("bounds"))
        t0 = time.time()
        adb.tap(x, y)
        adb.wait_stable()
        waited_ms = int((time.time() - t0) * 1000)
        page = adb.get_current_page()
        try:
            from cache import store as _cs, config as _cc
            app_ver = _get_app_version_cached(adb, pkg)
            _cs.upsert(pkg, act, app_ver, query, query_type, x, y, cached_pos.get("bounds"))
        except Exception:
            pass
        return ok("tap",
                  target={"text": query, "center": [x, y], "cache_hit": True},
                  screenshot=evidence.get("screenshot"),
                  spotlight=evidence.get("spotlight"),
                  interaction={
                      "kind": "cache",
                      "selector": {"id": args.id} if args.id else {"text": args.text},
                      "reason": getattr(args, "reason", None),
                      "fallback": False,
                  },
                  page_before=page_before,
                  page_after=page,
                  waited_ms=waited_ms,
                  page_after_activity=page.get("activity", ""))

    # 缓存未命中 → dump + find
    elem = _resolve_element(adb, id_val=args.id, text_val=args.text)
    if not elem:
        return err_not_found("tap", query)
    if not elem.get("center"):
        return error("tap", "INVALID_BOUNDS", f"元素 '{query}' 没有有效坐标")

    x, y = elem["center"]
    evidence = _capture_action_evidence(
        adb, x=x, y=y, action="tap",
        bounds=elem.get("bounds"), target_id=elem.get("id"), target_text=elem.get("text"),
    )
    t0 = time.time()
    adb.tap(x, y)
    adb.wait_stable()
    waited_ms = int((time.time() - t0) * 1000)
    page = adb.get_current_page()

    if pkg and act:
        try:
            from cache import store as _cs, config as _cc
            if _cc.get("cache.enabled", True):
                app_ver = _get_app_version_cached(adb, pkg)
                _cs.upsert(pkg, act, app_ver, query, query_type, x, y, elem.get("bounds"))
        except Exception:
            pass

    return ok("tap",
              target={"text": elem["text"], "id": elem["id"], "center": [x, y]},
              screenshot=evidence.get("screenshot"),
              spotlight=evidence.get("spotlight"),
              interaction={
                  "kind": "structured-id" if args.id else "structured-text",
                  "selector": {"id": args.id} if args.id else {"text": args.text},
                  "reason": getattr(args, "reason", None),
                  "fallback": False,
              },
              page_before=page_before,
              page_after=page,
              waited_ms=waited_ms,
              page_after_activity=page.get("activity", ""))


# ── cmd_input ────────────────────────────────────────────────────

def cmd_input(adb: ADBClient, args) -> dict:
    query = args.id or args.text
    elem = _resolve_element(adb, id_val=args.id, text_val=args.text)
    if not elem:
        return err_not_found("input", query)

    try:
        page_before = adb.get_current_page()
    except Exception:
        page_before = {}

    x, y = elem["center"]
    evidence = _capture_action_evidence(
        adb, x=x, y=y, action="input-focus",
        bounds=elem.get("bounds"), target_id=elem.get("id"), target_text=elem.get("text"),
    )
    adb.tap(x, y)
    time.sleep(0.3)
    adb.input_text(args.value)
    try:
        page_after = adb.get_current_page()
    except Exception:
        page_after = {}

    return ok("input",
              target={"id": elem["id"], "text": elem["text"]},
              value=args.value,
              screenshot=evidence.get("screenshot"),
              spotlight=evidence.get("spotlight"),
              interaction={
                  "kind": "structured-id" if args.id else "structured-text",
                  "selector": {"id": args.id} if args.id else {"text": args.text},
                  "reason": None, "fallback": False,
              },
              page_before=page_before,
              page_after=page_after)


# ── cmd_scroll ───────────────────────────────────────────────────

def cmd_scroll(adb: ADBClient, direction: str) -> dict:
    try:
        page_before = adb.get_current_page()
    except Exception:
        page_before = {}

    info = adb.get_device_info()
    res = info.get("resolution", "1080x2400").split("x")
    w, h = int(res[0]), int(res[1])
    cx = w // 2

    scroll_map = {
        "up":    (cx, int(h * 0.7), cx, int(h * 0.3)),
        "down":  (cx, int(h * 0.3), cx, int(h * 0.7)),
        "left":  (int(w * 0.8), h // 2, int(w * 0.2), h // 2),
        "right": (int(w * 0.2), h // 2, int(w * 0.8), h // 2),
    }
    if direction not in scroll_map:
        return error("scroll", "INVALID_DIRECTION",
                     f"不支持的方向 '{direction}'，可选：up / down / left / right")

    x1, y1, x2, y2 = scroll_map[direction]
    adb.swipe(x1, y1, x2, y2, duration_ms=400)
    adb.wait_stable()
    try:
        page_after = adb.get_current_page()
    except Exception:
        page_after = {}
    return ok("scroll", direction=direction,
              page_before=page_before, page_after=page_after)


# ── cmd_back / cmd_keyevent ──────────────────────────────────────

def cmd_back(adb: ADBClient) -> dict:
    try:
        page_before = adb.get_current_page()
    except Exception:
        page_before = {}
    adb.keyevent("back")
    adb.wait_stable()
    page = adb.get_current_page()
    return ok("back", page_before=page_before, page_after=page,
              page_after_activity=page.get("activity", ""))


def cmd_keyevent(adb: ADBClient, key: str) -> dict:
    adb.keyevent(key)
    adb.wait_stable()
    return ok("keyevent", key=key)
