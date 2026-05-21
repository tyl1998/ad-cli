"""全局配置管理 (~/.ad-cli/config.json)"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_AD_CLI_DIR = Path.home() / ".ad-cli"
_CONFIG_PATH = _AD_CLI_DIR / "config.json"

_DEFAULTS: dict = {
    "cache": {
        "confidence_threshold": 1,  # 命中多少次才信任缓存坐标
        "ttl_days": 7,              # 坐标缓存过期天数
        "enabled": True,            # 全局开关
        "hamming_threshold": 10,    # pHash 汉明距离阈值（0=完全相同，64=完全不同）
    },
    "replay": {
        "default_generate_report": False,  # 回放时是否默认生成报告
        "speed_factor": 1.0,               # 回放速度倍率（0.5=慢放，2.0=快放）
    },
    "mirror": {
        "default_mode": "window",
        "default_port": 8888,
        "recordings_dir": str(Path.home() / ".ad-cli" / "recordings"),
    },
    "adb": {
        "default_serial": None,
    },
}


def _ensure_dir() -> None:
    _AD_CLI_DIR.mkdir(parents=True, exist_ok=True)


def _deep_copy(d: Any) -> Any:
    return copy.deepcopy(d)


def _merge(defaults: dict, overrides: dict) -> dict:
    result = _deep_copy(defaults)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def load() -> dict:
    """加载配置，不存在时返回默认值"""
    _ensure_dir()
    if not _CONFIG_PATH.exists():
        return _deep_copy(_DEFAULTS)
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _merge(_DEFAULTS, data)
    except Exception:
        return _deep_copy(_DEFAULTS)


def save(config: dict) -> None:
    """保存配置到磁盘"""
    _ensure_dir()
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get(key_path: str, default: Any = None) -> Any:
    """读取配置值，key_path 格式: 'cache.confidence_threshold'"""
    cfg = load()
    keys = key_path.split(".")
    cur = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def set_value(key_path: str, value: Any) -> None:
    """写入配置值，key_path 格式: 'cache.confidence_threshold'"""
    cfg = load()
    keys = key_path.split(".")
    cur = cfg
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value
    save(cfg)
