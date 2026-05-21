# ad-cli 项目文档

## 项目概述
构建一个类似 Playwright CLI 的 Android 应用自动化工具，通过 ADB 连接手机获取 UI 元素信息，转换为结构化数据，发送给 AI 进行分析和操作。

---

## ✅ 已验证的技术方案

### 1. 获取原生 App UI（已验证可行）

```bash
adb shell uiautomator dump /sdcard/window_dump.xml
adb pull /sdcard/window_dump.xml
```

**无需安装任何工具**，Android 4.1+ 系统自带，直接可用。

#### 能获取到的信息（实验于星巴克 App）
- ✅ 完整 UI 树，嵌套深达 **21 层**，共 **198 个元素**
- ✅ 元素类型（TextView, ImageView, ViewGroup 等）
- ✅ 文本内容（商品名、价格、按钮文字等）
- ✅ 资源 ID（`resource-id`），**85% 的元素有 ID**，定位精准
- ✅ 精确坐标（`bounds`），可直接用于 `adb input tap`
- ✅ 交互属性（clickable / scrollable / long-clickable）
- ✅ 37 个可交互元素，26 个底层文本元素

#### 数据流
```
adb dump → XML → Python 解析 → JSON → AI 分析
```

---

### 2. 微信小程序（已验证：不可行）

`uiautomator dump` 对微信小程序**无效**，原因：
- 微信使用自研 **XWeb 引擎**（非标准 Android View）
- XWeb 没有暴露 Chrome DevTools Protocol 调试接口
- `dump` 结果只返回一个空壳节点（412 bytes）

**替代方案（按优先级）：**
1. 本地 OCR（PaddleOCR）截图识别 → 零 token 消耗
2. 坐标盲操作（截图确定位置 → `adb input tap x y`）
3. 微信开发者工具真机调试（需要是该小程序的开发者）

---

## 📁 项目结构

```
ad-cli/
├── CLAUDE.md              # 项目文档（本文件）
├── .venv/                 # ⭐ 唯一 Python 环境（Python 3.10.1）
│                          #   包含：scrcpy-client, opencv-python, PySide6
├── src/
│   ├── main.py            # ⭐ CLI 入口（266 行薄路由层），仅做参数解析 + 分发
│   │
│   ├── core/              # 基础设施层（实际业务代码）
│   │   ├── adb_client.py  # ADB 底层封装
│   │   ├── output.py      # 统一 JSON 输出格式
│   │   ├── ui_parser.py   # XML 解析 + compact/full + 精确/模糊查找
│   │   └── app_manager.py # App 安装/启动/查询
│   │
│   ├── commands/          # 命令层（由 main.py 导入）
│   │   ├── action.py      # tap / input / scroll / back / keyevent
│   │   ├── perception.py  # dump / find / screenshot / exists / get-text / wait
│   │   ├── report_cmd.py  # report 子命令 + maybe_record_execution
│   │   ├── app.py         # app 子命令（转发 core/app_manager）
│   │   └── system.py      # device / page 命令
│   │
│   ├── subsystems/
│   │   ├── mirror/
│   │   │   ├── scrcpy_server.py  # 投屏服务器（PySide6 窗口 + MJPEG Web）
│   │   │   ├── recorder.py       # RecordingState（录制状态机，已从 server 中提取）
│   │   │   └── server.py         # 薄代理（供外部 import）
│   │   └── replay/
│   │       ├── replay.py         # replay_report / replay_recording 实现
│   │       └── __init__.py       # re-export
│   │
│   ├── cache/             # 元素坐标缓存模块
│   │   ├── store.py       # SQLite 读写（含 pHash label 缓存）
│   │   ├── config.py      # ~/.ad-cli/config.json 管理
│   │   └── phash.py       # 纯 Pillow pHash（无 numpy/cv2）
│   │
│   ├── report/            # 报告模块
│   │   ├── manager.py        # 报告生命周期管理
│   │   ├── html_renderer.py  # HTML 生成（单报告 + 根目录 suite index）
│   │   ├── analysis.py       # 分析工具
│   │   ├── assets.py         # 静态资源
│   │   └── utils.py          # 工具函数
│   │
│   ├── scripts/           # 独立工具脚本（不在主流程中）
│   │   ├── rebuild_report_assets.py
│   │   ├── realtime_cleaner.py
│   │   ├── analyze_ui_depth.py
│   │   ├── generate_structure.py
│   │   └── visualize_hierarchy.py
│   │
│   └── *.py (compat shims)  # adb_client / output / ui_parser / app_manager /
│                             # replay / scrcpy_server / report_manager
│                             # 均为 1-3 行转发 shim，保持向后兼容
│
├── report/                # 报告产物目录
│   ├── index.html         # ⭐ 用例集总览首页（自动生成，风格与子报告一致）
│   └── <run-id>/
│       ├── index.html     # 单次执行详情报告
│       └── ...
├── screenshot/            # 截图保存目录（项目根，非 src/）
└── docs/
```

### 运行方式
```bash
cd src
python3 main.py <command> [args]
# 投屏
python3 main.py mirror                     # PySide6 窗口模式
python3 main.py mirror --mode web          # 浏览器 MJPEG 模式
```

### 环境说明
- `.venv`（Python 3.10.1）：项目唯一 Python 环境，含所有依赖
- `main.py` 直接用 `.venv/bin/python` 启动 `scrcpy_server.py`
- `.vscode/tasks.json` 中所有任务均使用 `source .venv/bin/activate`

---

---

## 🛠️ CLI 命令设计

### 一、系统级

| 命令 | 作用 | 说明 |
|------|------|------|
| `device info` | 设备基本信息 | 型号、系统版本、分辨率 |
| `app list` | 已安装且可启动的 App | 返回包名 + App 名，过滤系统内部服务 |
| `app info <package>` | 查某个 App 详情 | 是否安装、版本号、是否运行中 |
| `app launch <package>` | 启动 App | 启动后等待页面稳定再返回 |
| `app stop <package>` | 关闭 App | |
| `app install <apk_path>` | 安装 App | AI 找不到 App 时，提示用户提供 apk 路径后调用 |
| `page info` | 当前页面信息 | 包名 + Activity 名 |
| `report start <suite_name>` | 开启一份执行报告 | 一个用例集对应一个报告目录 |
| `report status` | 查看当前报告状态 | 当前 suite、case 数、步骤数 |
| `report case-start <case_name>` | 开启一个测试 case | 后续步骤自动归属到该 case |
| `report case-end` | 结束当前 case | 可标记 passed/failed/skipped |
| `report case-pass` | 快速结束当前 case | 等价于 `report case-end --status passed` |
| `report case-fail` | 快速结束当前 case | 等价于 `report case-end --status failed` |
| `report case-skip` | 快速结束当前 case | 等价于 `report case-end --status skipped` |
| `report note <title>` | 写入一条 AI/人工备注 | 可附带内容、级别和截图 |
| `report finalize` | 完成报告 | 默认要求先结束当前 case；可用 `--force` 强制收口 |
| `report serve [report_dir]` | 启动报告预览服务 | 自动定位 active/最新报告，并返回本地访问 URL |

> **`app list` 说明**：只返回有桌面 icon 的可启动 App（`CATEGORY_LAUNCHER`），过滤系统服务进程，避免返回几百个无用包名。

> **`app install` 流程**：AI 调用 `app info` 发现 `installed: false` → 返回 `APP_NOT_INSTALLED` 错误 + 提示语 → AI 询问用户提供 apk 路径 → 调用 `app install <path>`。

> **报告生命周期**：一个用例集对应一个目录；目录下包含多个 case，每个 case 下的命令执行过程自动追加到同一份报告中。

### 报告目录结构

默认输出到 `./report/<run-id>/`，也可在 `report start` 时通过 `--output-dir` 指定。

```
report/<run-id>/
├── index.html              # 可直接打开的执行报告
├── report.json             # 聚合后的完整报告 JSON
├── executions/
│   ├── exec-0001.execution.json
│   └── exec-0002.execution.json
└── screenshots/
  ├── exec-0001.png
  └── exec-0002.png
```

### 报告页面能力

- 左侧 `Cases` 侧栏：查看所有 case、状态与步骤数
- 中间 `Timeline` 时间线：查看当前 case 的执行步骤序列
- 右侧 `Viewer` 面板：包含 `播放` / `详情` 双 tab
- `播放` tab：优先直接展示步骤截图，并支持按时间线自动播放图片帧
- 点击类步骤会自动留证截图，并在播放页直接展示带标注的证据图
- `详情` tab：查看 case 结论卡片、业务步骤、证据检查点、页面前后对比、dump 摘要、返回 JSON
- 报告会区分 `业务步骤` 与 `原子 execution`，便于业务复盘与技术排障
- 报告会区分 `evidence checkpoint` 与普通 supporting screenshot，突出关键证据
- 支持点击时间线步骤切换详情，适合 QA 回放与排查

### 报告预览

- 执行 `report serve` 时，若不传路径，优先预览当前 active report；若没有 active report，则自动选择最新一份报告
- 也可显式指定报告目录：`report serve ./report/<run-id>`
- 默认端口为 `8765`，可通过 `--port` 指定

---

### 二、感知类

| 命令 | 默认行为 | 异常回退 |
|------|---------|----------|
| `dump` | 只返回可交互元素 + 有文本元素 | 返回 0 个时自动切全量 + **自动截图** |
| `dump --screenshot` | 同上，强制附带截图 | — |
| `find <query>` | 精确匹配 id / text / class | 找不到时返回模糊候选列表 |
| `screenshot [path]` | 截图保存到当前工作目录 | 返回本地文件路径 |

> **截图说明：**
> - 截图文件保存到**命令运行目录**，文件名带时间戳（如 `ad_cli_screen_170250.png`）
> - 手机上的临时截图文件**自动删除**，不占用手机存储
> - `dump` 在 full 模式回退时**自动触发截图**，返回中包含 `screenshot` 路径和 `hint` 提示
> - AI 拿到截图路径后可结合 `tap --xy x y` 进行坐标操作

---

### 三、操作类

| 命令 | 定位优先级 | 等待策略 |
|------|-----------|---------|
| `tap` | `label(pHash缓存) > id > text > xy坐标` | 点击后等页面稳定（默认 2s 超时） |
| `input` | `id > text` | 完成后返回 |
| `scroll` | `direction: up/down/left/right` | 滑动后等稳定 |
| `back` | 无 | 等页面稳定 |
| `keyevent <key>` | home / enter / del 等 | 等稳定 |

> **点击留证说明：** `tap` 与 `input` 在执行前会自动截图，并把点击坐标、元素 bounds、目标 id/text 一并写入报告 execution，便于在 HTML 报告中回放点击位置。
>
> **点击解释说明：** `tap` 支持 `--reason`，可把“为什么点这里”写进报告，帮助区分结构化点击、坐标点击和兜底点击策略。>
> **pHash 标签缓存模式：** 对于微信小程序等无法 `dump` 的页面，用 `tap --xy X Y --label 名称` 首次写入缓存（记录截图 pHash 作为页面指纹），后续 `tap --label 名称` 直接命中缓存点击，无需 dump 也无需提供坐标。pHash 汉明距离 ≤ 10 视为同一页面，防止跨页面误命中。
---

### 四、断言类

| 命令 | 输出 |
|------|------|
| `exists <query>` | `true / false` |
| `get-text <query>` | 文本字符串 |
| `wait <query>` | 出现返回元素信息，超时返回 error |

---

## 📐 输出格式规范

所有命令统一返回 JSON，结构固定：

```json
{ "status": "ok | error", "command": "命令名", "data": {} }
```

### 典型返回示例

**`app list`**
```json
{
  "status": "ok",
  "command": "app list",
  "data": [
    { "package": "com.starbucks.cn", "name": "星巴克" },
    { "package": "com.tencent.mm",   "name": "微信" }
  ]
}
```

**`app info` - App 未安装**
```json
{
  "status": "error",
  "command": "app info",
  "code": "APP_NOT_INSTALLED",
  "message": "未找到 com.starbucks.cn，该 App 可能未安装",
  "hint": "可调用 app install <apk_path> 进行安装"
}
```

**`dump` - 默认精简模式**
```json
{
  "status": "ok",
  "command": "dump",
  "mode": "compact",
  "total_elements": 198,
  "returned": 37,
  "data": [
    { "type": "TextView",  "text": "去结算",  "id": "tvSubmit",     "center": [900, 2142], "clickable": true },
    { "type": "TextView",  "text": "3张好礼券","id": "tvCouponCount","center": [200, 2142], "clickable": true }
  ]
}
```

**`dump` - 自动回退全量（含自动截图）**
```json
{
  "status": "ok",
  "command": "dump",
  "mode": "full",
  "reason": "compact 模式返回 0 个元素，已自动切换全量",
  "total_elements": 1,
  "returned": 1,
  "screenshot": "/path/to/project/src/ad_cli_screen_170250.png",
  "hint": "已自动截图，可结合图片辅助判断页面内容",
  "data": [...]
}
```

**`dump --screenshot` - 强制带截图**
```json
{
  "status": "ok",
  "command": "dump",
  "mode": "compact",
  "total_elements": 141,
  "returned": 51,
  "screenshot": "/path/to/project/src/ad_cli_screen_170250.png",
  "data": [...]
}
```

**`find` - 精确命中**
```json
{
  "status": "ok",
  "command": "find",
  "matched": "exact",
  "data": { "id": "tvSubmit", "text": "去结算", "center": [900, 2142], "clickable": true }
}
```

**`find` - 找不到，返回模糊候选**
```json
{
  "status": "ok",
  "command": "find",
  "matched": "fuzzy",
  "message": "未找到精确匹配，以下是相似结果，请 AI 判断是否符合预期",
  "candidates": [
    { "text": "去结算",  "similarity": 0.9, "center": [900, 2142] },
    { "text": "结算中心","similarity": 0.6, "center": [540, 1800] }
  ]
}
```

**`tap` - 成功**
```json
{
  "status": "ok",
  "command": "tap",
  "target": { "text": "去结算", "center": [900, 2142] },
  "waited_ms": 800,
  "page_after": "com.starbucks.cn/.CheckoutActivity"
}
```

**通用错误**
```json
{
  "status": "error",
  "command": "tap",
  "code": "ELEMENT_NOT_FOUND",
  "message": "找不到 text='去结算' 的元素，建议先调用 dump 确认当前页面元素"
}
```

---

## 🔑 Error Code 规范

| code | 含义 |
|------|------|
| `ELEMENT_NOT_FOUND` | 元素不存在 |
| `AMBIGUOUS_MATCH` | 匹配到多个元素 |
| `APP_NOT_INSTALLED` | App 未安装 |
| `APP_NOT_RUNNING` | App 未在前台 |
| `DEVICE_DISCONNECTED` | 设备未连接 |
| `TIMEOUT` | 等待超时 |
| `PERMISSION_DENIED` | ADB 权限不足 |

---

## 🚀 下一步：实现计划

```
src/
├── main.py          # CLI 入口，命令路由
├── adb_client.py    # ADB 底层封装
├── ui_parser.py     # XML 解析 + 精简/全量模式
├── app_manager.py   # App 安装/启动/查询
└── output.py        # 统一 JSON 输出格式
```

实现顺序：
1. `output.py` — 先定好输出格式
2. `adb_client.py` — ADB 基础操作封装
3. `app_manager.py` — 系统级命令
4. `ui_parser.py` — dump / find 逻辑
5. `main.py` — 串联所有命令

---

## ✅ 最新实现状态（2026-05-20）

### 代码结构重构（已完成）
- `main.py` 从 1130 行缩减到 **266 行**，纯路由层，不含任何业务逻辑
- 所有命令实现迁移至 `commands/`（action / perception / report_cmd / app / system）
- 基础设施（adb_client / output / ui_parser / app_manager）迁移至 `core/`
- `scrcpy_server.py` 迁移至 `subsystems/mirror/`；`replay.py` 迁移至 `subsystems/replay/`
- 原位留 1-3 行 compat shim，已有引用无需修改
- 独立工具脚本归入 `scripts/`，不污染主模块命名空间

### 元素坐标缓存（已完成）
- `cache/store.py`：SQLite，UNIQUE 键 `(package, activity, app_version, query, query_type)`
- TTL 失效：`app_version` 变更 或 超过 `ttl_days`（默认 7 天）
- `app_version` 懒加载：进程启动时查询一次，缓存到 `_APP_VERSION_CACHE` 字典
- 置信度默认 1（首次命中即信任），可通过 `cache set-confidence N` 修改

### pHash 截图标签缓存（已完成）
- 解决微信小程序等**无法 dump** 页面的缓存问题
- 原理：截图的**感知哈希（pHash）**作为页面指纹，汉明距离 ≤ 10 认为是同一页面
- 实现：`cache/phash.py`（纯 Pillow，无 numpy/cv2），8×8 DCT pHash
- 用法：
  ```bash
  # 第一次：--xy 点击 + --label 写入缓存（截图 pHash 作为页面指纹）
  ad-cli tap --xy 540 1200 --label "登录按钮"

  # 后续：只用 --label，命中缓存直接点击，无需 dump 也无需 xy
  ad-cli tap --label "登录按钮"
  ```
- pHash 存储在 `element_cache.page_hash` 列，查询时按汉明距离模糊匹配
- 同一张图 hamming = 0；轻微 UI 变化 hamming ≈ 3~6；页面切换 hamming > 20

### 录制功能（⚠️ 不成熟，回放通过率极低）
- `ad-cli mirror --record <name>` 打开投屏窗口并进入录制模式
- Window 模式底部工具栏：`● 开始录制` / `⏸ 暂停` / `■ 结束并保存`
- Web 模式叠加录制控制条，通过 `/record/start|pause|stop` HTTP 端点控制
- 产物：`~/.ad-cli/recordings/<name>_<timestamp>.replay.json`（结构化 JSON，含 delay_before_ms）
- **已知问题**：纯坐标回放，无页面状态感知；App 动态内容（推荐位、门店列表顺序等）变化后坐标全部失效；实测回放通过率接近 0

### 回放功能（⚠️ 录制回放不成熟，报告回放相对可用）
- `ad-cli replay [name]`：回放指定报告目录的业务步骤（仅 tap/input/scroll 等操作类）
- `ad-cli replay [name] --full`：回放全量步骤（含 dump/wait，还原真实时序）
- `ad-cli replay <name> --recording`：回放手动录制脚本
- `--speed <factor>`：调整回放速度；`--dry-run`：仅打印不执行

### 投屏功能
- `--mode window`：PySide6 QMainWindow + QLabel，无白边，支持拖拽缩放，鼠标触控映射
- `--mode web`：极简 socket HTTP MJPEG 服务，自动打开浏览器，支持触控映射
- `--sharpen`：window 模式开启锐化滤镜
- 截图固定保存到 `<项目根>/screenshot/`，不受 `os.getcwd()` 影响

### 报告用例集首页
- `finalize()` 和 `start_report()` 后自动更新 `report/index.html`
- `report serve` 返回 `root_url`（总览页）和 `url`（本次 run 详情）两个地址

---

## 🗺️ 功能规划：回放 + 缓存 + 录制（2026-05-20 讨论决策）

### 一、总体约束：二进制打包

最终形态需打包为单一二进制可执行文件（PyInstaller `--onefile`），需满足：

- `mirror` 子进程不再依赖 `.venv`，改为：
  ```python
  scrcpy_python = (
      sys.executable   # PyInstaller 打包后 sys.frozen=True，指向二进制自身
      if getattr(sys, "frozen", False)
      else os.path.join(project_root, ".venv", "bin", "python")  # 开发模式
  )
  ```
- 所有依赖（scrcpy-client, opencv, PySide6, SQLite）随二进制内嵌
- 全局缓存/配置路径使用 `~/.ad-cli/`，与二进制安装位置无关

---

### 二、元素坐标缓存

#### 存储位置
```
~/.ad-cli/
  cache/
    elements.db          # SQLite 主缓存
  recordings/
    <name>_<timestamp>.replay.json
  config.json
```

#### SQLite Schema
```sql
CREATE TABLE element_cache (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  package       TEXT    NOT NULL,
  activity      TEXT    NOT NULL,
  app_version   TEXT    NOT NULL DEFAULT '',
  query         TEXT    NOT NULL,
  query_type    TEXT    NOT NULL,   -- 'text' | 'id'
  center_x      INTEGER NOT NULL,
  center_y      INTEGER NOT NULL,
  bounds        TEXT,
  hit_count     INTEGER DEFAULT 1,
  last_seen_ts  INTEGER NOT NULL,
  source_exec   TEXT,
  UNIQUE(package, activity, app_version, query, query_type)
);
CREATE INDEX idx_lookup ON element_cache(package, activity, app_version, query);
```

#### TTL 失效规则（复合判断）
1. `app_version` 变更 → 立即失效
2. 超过 `ttl_days`（默认 7 天）→ 失效

#### `app_version` 懒加载策略（已决策）
- **只在执行测试集启动时查询一次**，缓存到进程内存（`_APP_VERSION_CACHE: dict`）
- 不在每次 `tap/find` 前重复查询，避免增加延迟

#### 置信度配置（已决策）
- 默认 `confidence_threshold = 1`（1次命中即信任）
- 可在 `~/.ad-cli/config.json` 中调整

---

### 三、全局配置文件

**路径：`~/.ad-cli/config.json`**

```json
{
  "cache": {
    "confidence_threshold": 1,
    "ttl_days": 7,
    "enabled": true
  },
  "replay": {
    "default_generate_report": false,
    "speed_factor": 1.0
  },
  "mirror": {
    "default_mode": "window",
    "default_port": 8888,
    "recordings_dir": "~/.ad-cli/recordings"
  },
  "adb": {
    "default_serial": null
  }
}
```

---

### 四、回放（Replay）

#### 数据源
复用已有 `executions/*.execution.json`，每条记录含 `argv` + `started_at` + `ended_at`。

#### 时间还原
```python
duration = execution["ended_at_ts"] - execution["started_at_ts"]  # 毫秒
time.sleep(duration / 1000)
```

#### 命令设计
```bash
# 回放成功 case 的业务步骤（只含 tap/input/scroll/back/keyevent）
ad-cli replay --report <dir_name>

# 回放失败 case 全量步骤（含 dump/wait，时间一致）
ad-cli replay --report <dir_name> --full

# 只回放指定 case
ad-cli replay --report <dir_name> --case <case_id>

# 回放时生成新报告（可选，默认不生成）
ad-cli replay --report <dir_name> --generate-report

# 回放手动录制脚本
ad-cli replay --recording <name>
```

---

### 五、录制（Record）

#### 触发方式
```bash
ad-cli mirror --record <name>   # 打开投屏窗口并进入录制模式
```

#### 录制产物（已决策：结构化 JSON）
```json
{
  "version": "1.0",
  "meta": {
    "name": "starbucks_login",
    "device": "emulator-5554",
    "resolution": [1080, 2400],
    "recorded_at": "2026-05-20T10:00:00",
    "app_package": "com.starbucks.cn"
  },
  "steps": [
    {"seq": 1, "type": "tap",     "x": 540, "y": 1200, "delay_before_ms": 0},
    {"seq": 2, "type": "input",   "text": "13800138000", "delay_before_ms": 800},
    {"seq": 3, "type": "swipe",   "x1": 540, "y1": 1600, "x2": 540, "y2": 800, "duration_ms": 400, "delay_before_ms": 1200},
    {"seq": 4, "type": "keyevent","key": "back", "delay_before_ms": 600}
  ]
}
```

- **不包含截图**（已决策）
- `delay_before_ms` = 该步骤与上一步骤的真实时间间隔
- 保存到 `~/.ad-cli/recordings/<name>_<timestamp>.replay.json`

#### 录制 UI 控件（已决策：页面内按钮）

**Window 模式（PySide6）**：底部工具栏增加三个按钮
```
[ ● 开始录制 ]  [ ⏸ 暂停 ]  [ ■ 结束并保存 ]
```
- 开始录制 → 显示红色录制指示，捕获 `mousePressEvent` / `keyPressEvent`
- 暂停 → 暂停计时和事件捕获，按钮变为「▶ 继续」
- 结束并保存 → 弹出命名输入框，写入 JSON 文件

**Web 模式**：在 MJPEG 页面叠加控制条（HTML/JS），点击事件通过 `/record-event` HTTP POST 回传 Python server。

#### 坐标映射
录制时鼠标坐标为 PC 窗口坐标，需反算回设备真实分辨率坐标：
```python
device_x = int(mouse_x / scale_factor)
device_y = int(mouse_y / scale_factor)
```
`scale_factor` 已在 `scrcpy_server.py` 中维护。

---

### 六、缓存管理命令
```bash
ad-cli cache stats                              # 查看条目数、命中率统计
ad-cli cache clear                              # 清空全部缓存
ad-cli cache clear --package com.starbucks.cn  # 清空指定包缓存
ad-cli cache set-confidence 2                  # 修改置信度阈值（写入 config.json）
```

### 七、pHash 标签缓存（针对无 dump 页面）

#### 使用场景
微信小程序、WebView 等 `uiautomator dump` 无效的页面，只能坐标点击。

#### 工作流程

| 步骤 | 命令 | 行为 |
|------|------|------|
| 首次（写缓存） | `tap --xy 540 1200 --label 登录按钮` | 截图 → 计算 pHash → 写入 `element_cache(label, page_hash, x, y)` |
| 后续（命中缓存） | `tap --label 登录按钮` | 截图 → 计算 pHash → 汉明距离 ≤ 10 → 直接 tap(x, y)，跳过 dump |

#### pHash 技术细节
- 实现：`cache/phash.py`，纯 Pillow，无 numpy/cv2 依赖
- 算法：8×8 DCT，输出 64-bit 整数
- 相似阈值：`hamming_threshold = 10`（可在 `~/.ad-cli/config.json` 调整）
- 同一张图 hamming = 0；轻微 UI 变化（弹窗等）hamming ≈ 3~6；页面切换 hamming > 20

