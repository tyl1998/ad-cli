"""元素坐标缓存 & 全局配置包"""
from .store import lookup, upsert, lookup_label, upsert_label, clear, stats
from . import config
from . import phash

__all__ = ["lookup", "upsert", "lookup_label", "upsert_label",
           "clear", "stats", "config", "phash"]
