"""
报告截图资产处理模块
- persist_visual_assets:  复制原始截图，生成 focus_preview
- build_focus_preview:    裁剪区域并绘制点击准星
- _can_use_direct_mapping / _parse_bounds: 坐标映射辅助
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Any

from PIL import Image, ImageDraw


def screenshots_dir(report_dir: str) -> str:
    return os.path.join(report_dir, "screenshots")


def persist_visual_assets(
    report_dir: str,
    execution_id: str,
    screenshot_source: str | None,
    spotlight: dict | None = None,
) -> dict[str, str | None]:
    """
    复制原始截图到报告目录（不修改原图），
    若有 spotlight 则另行生成聚焦预览图。
    返回 {"screenshot": 相对路径, "focus_preview": 相对路径或 None}
    """
    if not screenshot_source or not os.path.exists(screenshot_source):
        return {"screenshot": None, "focus_preview": None}

    ext = os.path.splitext(screenshot_source)[1] or ".png"
    file_name = f"{execution_id}{ext}"
    dest_abs = os.path.join(screenshots_dir(report_dir), file_name)
    shutil.copy2(screenshot_source, dest_abs)

    focus_preview = None
    if spotlight:
        try:
            focus_preview = build_focus_preview(report_dir, execution_id, dest_abs, spotlight)
        except Exception:
            focus_preview = None

    return {
        "screenshot": f"./screenshots/{file_name}",
        "focus_preview": focus_preview,
    }


def build_focus_preview(
    report_dir: str,
    execution_id: str,
    image_path: str,
    spotlight: dict,
) -> str | None:
    """裁剪聚焦区域并绘制点击准星，保存为 exec-XXXX.focus.png"""
    with Image.open(image_path) as img:
        image = img.convert("RGBA")

    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    viewport = spotlight.get("viewport") or {}
    viewport_w = int(viewport.get("width") or width or 1)
    viewport_h = int(viewport.get("height") or height or 1)

    bounds = _parse_bounds(spotlight.get("bounds"))
    use_direct = _can_use_direct_mapping(
        width=width,
        height=height,
        x=spotlight.get("x"),
        y=spotlight.get("y"),
        bounds=bounds,
    )

    def map_x(v: int | float) -> int:
        return int(float(v)) if use_direct else int((float(v) / viewport_w) * width)

    def map_y(v: int | float) -> int:
        return int(float(v)) if use_direct else int((float(v) / viewport_h) * height)

    if spotlight.get("x") is None or spotlight.get("y") is None:
        return None

    cx = map_x(spotlight["x"])
    cy = map_y(spotlight["y"])
    preview_margin = max(90, min(width, height) // 8)

    if bounds:
        left   = max(0,      map_x(bounds["x1"]) - preview_margin)
        top    = max(0,      map_y(bounds["y1"]) - preview_margin)
        right  = min(width,  map_x(bounds["x2"]) + preview_margin)
        bottom = min(height, map_y(bounds["y2"]) + preview_margin)
    else:
        left   = max(0,      cx - preview_margin * 2)
        top    = max(0,      cy - preview_margin * 2)
        right  = min(width,  cx + preview_margin * 2)
        bottom = min(height, cy + preview_margin * 2)

    focus_image = image.crop((left, top, right, bottom)).copy()
    focus_draw  = ImageDraw.Draw(focus_image, "RGBA")
    local_x = cx - left
    local_y = cy - top
    outer = max(18, min(width, height) // 25)
    inner = max(8, outer // 2)

    if bounds:
        lx1 = map_x(bounds["x1"]) - left
        ly1 = map_y(bounds["y1"]) - top
        lx2 = map_x(bounds["x2"]) - left
        ly2 = map_y(bounds["y2"]) - top
        focus_draw.rounded_rectangle(
            [(lx1, ly1), (lx2, ly2)],
            radius=14,
            outline=(59, 130, 246, 255),
            fill=(59, 130, 246, 28),
            width=4,
        )

    focus_draw.ellipse(
        [(local_x - outer, local_y - outer), (local_x + outer, local_y + outer)],
        outline=(255, 255, 255, 245),
        fill=(239, 68, 68, 52),
        width=4,
    )
    focus_draw.ellipse(
        [(local_x - inner, local_y - inner), (local_x + inner, local_y + inner)],
        fill=(239, 68, 68, 255),
        outline=(255, 255, 255, 255),
        width=3,
    )
    cross = max(10, inner + 4)
    focus_draw.line([(local_x - cross, local_y), (local_x + cross, local_y)],   fill=(255, 255, 255, 230), width=3)
    focus_draw.line([(local_x, local_y - cross), (local_x, local_y + cross)],   fill=(255, 255, 255, 230), width=3)

    preview_name = f"{execution_id}.focus.png"
    preview_abs  = os.path.join(screenshots_dir(report_dir), preview_name)
    focus_image.save(preview_abs)
    return f"./screenshots/{preview_name}"


def _can_use_direct_mapping(
    *,
    width: int,
    height: int,
    x: Any,
    y: Any,
    bounds: dict[str, int] | None,
) -> bool:
    if x is None or y is None:
        return False
    if float(x) > width or float(y) > height:
        return False
    if not bounds:
        return True
    return all(
        0 <= value <= limit
        for value, limit in (
            (bounds["x1"], width),
            (bounds["x2"], width),
            (bounds["y1"], height),
            (bounds["y2"], height),
        )
    )


def _parse_bounds(bounds: str | None) -> dict[str, int] | None:
    if not bounds:
        return None
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        return None
    return {
        "x1": int(match.group(1)),
        "y1": int(match.group(2)),
        "x2": int(match.group(3)),
        "y2": int(match.group(4)),
    }
