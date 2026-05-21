"""
感知哈希（pHash）工具 — 纯 Pillow 实现，无需 numpy/cv2。

算法：
  1. 将图像缩放到 32×32 灰度图
  2. 对每一行做 8 点离散余弦变换（DCT），取左上角 8×8 低频系数
  3. 计算 64 个系数的均值，每位与均值比较生成 64-bit 哈希

两张图的汉明距离 <= threshold（默认 10）即视为同一页面。
"""
from __future__ import annotations

import math
import struct


def _dct8(row: list[float]) -> list[float]:
    """8 点 1D DCT-II（Loeffler 近似），返回 8 个系数。"""
    N = 8
    out = []
    for k in range(N):
        s = sum(row[n] * math.cos(math.pi * k * (2 * n + 1) / (2 * N)) for n in range(N))
        out.append(s * math.sqrt(2.0 / N) * (1 / math.sqrt(2) if k == 0 else 1))
    return out


def compute(image_path: str, hash_size: int = 8) -> int:
    """
    计算图像的感知哈希，返回 64-bit 整数。
    image_path: 本地图片路径（PNG/JPG 均可）
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("pHash 需要 Pillow：pip install Pillow")

    img = Image.open(image_path).convert("L").resize(
        (hash_size * 4, hash_size * 4), Image.LANCZOS
    )

    # 转为像素矩阵（32×32）
    pixels = list(img.getdata())
    size = hash_size * 4
    matrix = [pixels[r * size:(r + 1) * size] for r in range(size)]

    # 2D DCT：先行后列，取左上 hash_size×hash_size 低频系数
    # 行 DCT（每行取前 hash_size 系数）
    row_dct = []
    for row in matrix:
        dct_row = []
        # 分段做 8 点 DCT（每段 8 点），覆盖 32 列
        for seg in range(size // 8):
            dct_row.extend(_dct8([float(v) for v in row[seg * 8:(seg + 1) * 8]]))
        row_dct.append(dct_row[:hash_size])  # 只保留前 hash_size 列

    # 列 DCT（对 hash_size 列，取前 hash_size 行系数）
    low_freq: list[float] = []
    for col in range(hash_size):
        col_vals = [row_dct[r][col] for r in range(size)]
        # 分段做 8 点 DCT
        col_dct: list[float] = []
        for seg in range(size // 8):
            col_dct.extend(_dct8(col_vals[seg * 8:(seg + 1) * 8]))
        low_freq.extend(col_dct[:hash_size])  # 只保留前 hash_size 行

    # 均值阈值 → 二进制哈希
    avg = sum(low_freq) / len(low_freq)
    bits = [1 if v > avg else 0 for v in low_freq]

    # 打包为 int（64-bit）
    result = 0
    for bit in bits:
        result = (result << 1) | bit
    return result


def hamming(h1: int, h2: int) -> int:
    """计算两个哈希值的汉明距离（不同位数）。"""
    x = h1 ^ h2
    dist = 0
    while x:
        dist += x & 1
        x >>= 1
    return dist


def similar(h1: int, h2: int, threshold: int = 10) -> bool:
    """汉明距离 <= threshold 时视为同一页面。"""
    return hamming(h1, h2) <= threshold


def to_hex(h: int) -> str:
    """哈希整数 → 16 位十六进制字符串（便于存储）。"""
    return f"{h:016x}"


def from_hex(s: str) -> int:
    """16 位十六进制字符串 → 哈希整数。"""
    return int(s, 16)
