"""
UI 解析模块
XML → 结构化元素列表，支持 compact/full 两种模式，以及精确/模糊查找
"""
import xml.etree.ElementTree as ET
import re
from difflib import SequenceMatcher


def _parse_bounds(bounds_str: str) -> dict | None:
    """解析 [x1,y1][x2,y2] 格式的坐标"""
    match = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
    if len(match) == 2:
        x1, y1 = int(match[0][0]), int(match[0][1])
        x2, y2 = int(match[1][0]), int(match[1][1])
        return {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        }
    return None


def _node_to_dict(node: ET.Element, depth: int = 0) -> dict:
    """将 XML node 转为字典"""
    bounds_info = _parse_bounds(node.get("bounds", ""))
    return {
        "type":        node.get("class", "").split(".")[-1],
        "text":        node.get("text", ""),
        "id":          node.get("resource-id", "").split("/")[-1],
        "resource_id": node.get("resource-id", ""),
        "content_desc":node.get("content-desc", ""),
        "clickable":   node.get("clickable") == "true",
        "long_clickable": node.get("long-clickable") == "true",
        "scrollable":  node.get("scrollable") == "true",
        "enabled":     node.get("enabled") == "true",
        "bounds":      node.get("bounds", ""),
        "center":      bounds_info["center"] if bounds_info else None,
        "depth":       depth,
    }


def _is_important(elem: dict) -> bool:
    """判断是否为 compact 模式下的重要元素：可交互 或 有文本"""
    return (
        elem["clickable"]
        or elem["long_clickable"]
        or elem["scrollable"]
        or bool(elem["text"].strip())
        or bool(elem["content_desc"].strip())
    )


def _flatten(node: ET.Element, depth: int = 0) -> list[dict]:
    """递归展平 UI 树为列表"""
    result = [_node_to_dict(node, depth)]
    for child in node:
        result.extend(_flatten(child, depth + 1))
    return result


def parse_xml(xml_content: str) -> list[dict]:
    """解析 XML 字符串，返回所有元素列表"""
    root = ET.fromstring(xml_content)
    elements = []
    for child in root:
        elements.extend(_flatten(child, 1))
    return elements


def compact(elements: list[dict]) -> list[dict]:
    """精简模式：只保留可交互 + 有文本的元素，并裁剪不必要字段"""
    important = [e for e in elements if _is_important(e)]
    # 返回给 AI 的字段尽量精简
    return [
        {k: v for k, v in e.items()
         if k in ("type", "text", "id", "content_desc", "center",
                  "clickable", "scrollable", "long_clickable", "bounds")}
        for e in important
    ]


# ── 查找逻辑 ──────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_exact(elements: list[dict], query: str) -> list[dict]:
    """
    精确查找，按优先级：
    1. resource_id 完整匹配
    2. id（短名）完整匹配
    3. text 完整匹配
    4. content_desc 完整匹配
    """
    results = []
    for e in elements:
        if (e["resource_id"] == query
                or e["id"] == query
                or e["text"] == query
                or e["content_desc"] == query):
            results.append(e)
    return results


def find_fuzzy(elements: list[dict], query: str, top_n: int = 5) -> list[dict]:
    """
    模糊查找，返回相似度最高的 top_n 个候选
    对 text / id / content_desc 分别计算相似度，取最大值
    """
    scored = []
    for e in elements:
        score = max(
            _similarity(query, e["text"]),
            _similarity(query, e["id"]),
            _similarity(query, e["content_desc"]),
        )
        if score > 0.3:
            scored.append((score, e))

    scored.sort(key=lambda x: x[0], reverse=True)

    candidates = []
    for score, e in scored[:top_n]:
        candidates.append({
            "type":     e["type"],
            "text":     e["text"],
            "id":       e["id"],
            "center":   e["center"],
            "bounds":   e["bounds"],
            "clickable":e["clickable"],
            "similarity": round(score, 2),
        })
    return candidates
