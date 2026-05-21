# src/ 代码结构审查与重构方案

> 审查日期：2026-05-20

## 一、当前结构总览

```
src/
├── main.py                # CLI 入口 (1130 行) ⚠️ 臃肿
├── adb_client.py          # ADB 底层封装 (257 行)
├── ui_parser.py           # UI XML 解析 (138 行)
├── app_manager.py         # App 管理命令 (72 行)
├── output.py              # JSON 输出格式 + ErrorCode (99 行)
├── report_manager.py      # 向后兼容层 — 薄壳 (14 行)
├── replay.py              # 回放模块 (283 行)
├── scrcpy_server.py       # 投屏模块 (911 行) ⚠️ 臃肿
├── realtime_cleaner.py    # 早期实验脚本 (329 行) 🗑️ 可删除
├── analyze_ui_depth.py    # 独立数据分析脚本 (155 行) 🗑️
├── generate_structure.py  # 独立可视化脚本 (154 行) 🗑️
├── visualize_hierarchy.py # 独立可视化脚本 (217 行) 🗑️
├── rebuild_report_assets.py # 一次性重建工具 (58 行)
├── .ad_cli_active_report.json
├── cache/                 # ✓ 缓存子系统 — 结构合理
│   ├── __init__.py
│   ├── config.py          # 全局配置管理 (~/.ad-cli/config.json)
│   ├── phash.py           # 感知哈希（pHash）纯 Pillow 实现
│   └── store.py           # SQLite 元素坐标缓存
└── report/                # ✓ 报告子系统 — 结构合理
    ├── __init__.py
    ├── manager.py         # ReportManager 主类 (488 行)
    ├── analysis.py        # 执行记录分析 & 业务步骤推导 (199 行)
    ├── assets.py          # 截图资产处理 & focus_preview (181 行)
    ├── html_renderer.py   # HTML 报告渲染 (1001 行) ⚠️ 偏大
    └── utils.py           # 工具函数 (43 行)
```

---

## 二、问题诊断

### 🔴 P0 — [`main.py`](src/main.py) 严重臃肿（1130 行）

**现状**：所有命令的实现函数（`cmd_dump`、`cmd_find`、`cmd_tap`、`cmd_input`、`cmd_wait` 等）全部写在 CLI 入口文件里，同时承担了：

- CLI 路由（`argparse` + `main()`）
- 命令实现（~650 行）
- 截图工具函数（`_take_screenshot`、`_capture_action_evidence`）
- Report 子命令路由（~250 行）

**影响**：新增命令成本高，修改一个命令容易误改另一个的上下文；lint 和 review 困难。

### 🔴 P0 — 根目录文件混杂

核心模块（`adb_client.py`、`ui_parser.py`）、独立子系统（`replay.py`、`scrcpy_server.py`）、实验脚本（`realtime_cleaner.py` 等 4 个）、工具脚本（`rebuild_report_assets.py`）全部平铺在 `src/`，没有按职责分层。

其中 `realtime_cleaner.py`、`analyze_ui_depth.py`、`generate_structure.py`、`visualize_hierarchy.py` 是早期实验/数据分析脚本，无命令行入口，不应与核心代码同层。

### 🟡 P1 — [`scrcpy_server.py`](src/scrcpy_server.py) 同类臃肿（911 行）

投屏模块将以下职责混在一个文件：

- scrcpy 客户端核心（视频流解码、控制通道）
- `RecordingState` 录制状态机
- PySide6 窗口渲染逻辑
- MJPEG Web 伺服 + 点击事件解析

**影响**：状态机、渲染、协议三层耦合，单独修改录制逻辑需要阅读 911 行文件。

### 🟡 P1 — `replay.py` 缺少命名空间

回放功能是独立子系统，目前单文件 `replay.py`。未来若增加录制回放对比等功能，需要一个独立目录来承载。

### 🟢 P2 — `report_manager.py` 薄壳兼容层

```python
# src/report_manager.py（14 行）
from report.manager import ReportManager
...
```

仅做 re-export，直接 `from report import ReportManager` 即可替代。

### 🟢 P2 — 缺少 Python 包规范化

- `src/` 根目录无 `__init__.py`
- 无 `pyproject.toml`，无法 `pip install -e .`

---

## 三、推荐目标结构

```
src/
├── __init__.py
├── main.py                    # CLI 入口（精简为路由 + argparse，~200 行）
│
├── core/                      # 核心基础设施
│   ├── __init__.py
│   ├── adb_client.py          # ← 原 adb_client.py
│   ├── output.py              # ← 原 output.py（JSON 输出 + ErrorCode）
│   └── ui_parser.py           # ← 原 ui_parser.py
│
├── commands/                  # 命令实现（按领域拆分）
│   ├── __init__.py
│   ├── system.py              # device info, page info
│   ├── app.py                 # app list/info/launch/stop/install
│   ├── perception.py          # dump, find, screenshot, exists, get-text, wait
│   ├── action.py              # tap, input, scroll, back, keyevent
│   └── report_cmd.py          # report start/case-*/note/finalize/serve
│
├── subsystems/                # 独立子系统
│   ├── __init__.py
│   ├── replay/                # 回放模块
│   │   ├── __init__.py
│   │   └── replay.py          # ← 原 replay.py
│   └── mirror/                # 投屏模块
│       ├── __init__.py
│       ├── server.py          # ← 原 scrcpy_server.py 核心
│       ├── recorder.py        # ← RecordingState 状态机
│       └── renderer.py        # ← PySide6 窗口 + MJPEG Web 伺服
│
├── report/                    # 报告子系统（保持现有结构 ✓）
│   ├── __init__.py
│   ├── manager.py
│   ├── analysis.py
│   ├── assets.py
│   ├── html_renderer.py
│   └── utils.py
│
├── cache/                     # 缓存子系统（保持现有结构 ✓）
│   ├── __init__.py
│   ├── config.py
│   ├── phash.py
│   └── store.py
│
├── report_manager.py          # 向后兼容层（保留，待 P2 阶段移除）
│
└── scripts/                   # 实验/工具脚本归档
    ├── analyze_ui_depth.py
    ├── generate_structure.py
    ├── visualize_hierarchy.py
    ├── realtime_cleaner.py
    └── rebuild_report_assets.py
```

---

## 四、拆分细节

### 4.1 [`main.py`](src/main.py) 拆分映射

| 函数/代码块 | 当前行数 | 迁移目标 |
|-------------|---------|---------|
| `_take_screenshot` | ~25 行 | `core/` 或 `commands/perception.py` |
| `_parse_resolution` | ~15 行 | `core/ui_parser.py` |
| `_capture_action_evidence` | ~20 行 | `commands/action.py` |
| `_get_app_version_cached` | ~10 行 | `core/adb_client.py` |
| `get_adb` / `get_report_manager` | ~10 行 | 保留在 `main.py` |
| `cmd_dump` | ~30 行 | `commands/perception.py` |
| `cmd_find` | ~30 行 | `commands/perception.py` |
| `cmd_exists` | ~15 行 | `commands/perception.py` |
| `cmd_get_text` | ~15 行 | `commands/perception.py` |
| `cmd_wait` | ~25 行 | `commands/perception.py` |
| `cmd_screenshot` | ~15 行 | `commands/perception.py` |
| `cmd_tap` | ~80 行 | `commands/action.py` |
| `cmd_input` | ~40 行 | `commands/action.py` |
| `cmd_scroll` | ~30 行 | `commands/action.py` |
| `cmd_back` | ~10 行 | `commands/action.py` |
| `cmd_keyevent` | ~10 行 | `commands/action.py` |
| Report CLI 子命令 | ~250 行 | `commands/report_cmd.py` |
| `argparse` 路由 + `main()` | ~200 行 | 保留在 `main.py` |

### 4.2 [`scrcpy_server.py`](src/scrcpy_server.py) 拆分

| 模块 | 职责 | 行数估算 |
|------|------|---------|
| `subsystems/mirror/server.py` | scrcpy 客户端核心（视频流解码、控制通道、设备信息） | ~400 行 |
| `subsystems/mirror/recorder.py` | `RecordingState` 录制状态机 + 结构化 JSON 导出 | ~250 行 |
| `subsystems/mirror/renderer.py` | PySide6 窗口渲染 + MJPEG Web 伺服 + 点击事件解析 | ~260 行 |

### 4.3 `scripts/` 归档

| 文件 | 说明 | 原因 |
|------|------|------|
| `realtime_cleaner.py` | 早期 UI 实时清洗实验 | CLAUDE.md 已标记"可删除"，无 CLI 入口 |
| `analyze_ui_depth.py` | UI 树深度分析 | 仅数据分析，无命令行调用 |
| `generate_structure.py` | UI 树结构图生成 | 仅可视化，无命令行调用 |
| `visualize_hierarchy.py` | UI 树嵌套可视化 | 仅可视化，无命令行调用 |
| `rebuild_report_assets.py` | 一次性重建工具 | 修复脚本，非常规功能 |

---

## 五、向后兼容

### 导入兼容

```python
# 旧用法（继续兼容，通过 report_manager.py 薄壳）
from report_manager import ReportManager

# 新用法（推荐）
from report import ReportManager
from report.manager import ReportManager
```

### CLI 兼容

`python3 main.py <command>` 调用方式完全不变，仅内部 import 路径调整。

---

## 六、执行优先级

| 优先级 | 任务 | 工作量 | 风险 |
|--------|------|--------|------|
| 🔴 P0-1 | 创建 `scripts/` 并移动 5 个实验/工具脚本 | 5 分钟 | 极低 |
| 🔴 P0-2 | 创建 `core/`、`commands/`，拆分 `main.py` | 1 小时 | 中（需逐函数迁移并验证） |
| 🟡 P1-1 | 创建 `subsystems/mirror/`，拆分 `scrcpy_server.py` | 30 分钟 | 中（需验证窗口/Web 两种模式） |
| 🟡 P1-2 | 创建 `subsystems/replay/`，移动 `replay.py` | 10 分钟 | 低 |
| 🟢 P2-1 | 补充 `src/__init__.py` + `pyproject.toml` | 10 分钟 | 极低 |
| 🟢 P2-2 | 移除 `report_manager.py` 薄壳，全局替换 import | 15 分钟 | 低 |

建议按 P0 → P1 → P2 顺序依次执行，每步验证后再进行下一步。