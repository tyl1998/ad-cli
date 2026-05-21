# ad-cli Skill

> **AI 阅读顺序：L0 → L1 → L2 → L3。L1 行为守则是强制规则，执行前必须内化。**

---

## L0 · 快速启动

```bash
ad-cli <command> [args]
```

所有输出均为 JSON。`status: "ok"` 成功，`status: "error"` 失败。

> **Tab 补全**：安装后 zsh/bash 自动生效（重开终端）；PowerShell 同样支持。
> 输入 `ad-cli ` 按 Tab 可补全所有子命令及参数。

### 标准流程骨架

```bash
ad-cli report start "用例集名称"
ad-cli report case-start "case 名称"
# ... 执行步骤 ...
ad-cli report case-end --status passed
ad-cli report finalize
# finalize 后：判断服务是否已启动，返回或启动报告预览
ad-cli report serve
```

### 感知命令优先级（从轻到重）

```
page info  →  find / exists / wait  →  dump  →  dump --screenshot  →  screenshot
```

原则：**先用最轻量的命令；结构化信息不足时才升级截图。**

---

## L1 · 行为守则（强制规则）

> 以下规则优先级高于一切，执行前必须遵守。

---

### 规则 A：权限弹窗 — 默认同意

**任何权限请求，默认点击同意，除非 case 明确要求拒绝。**

拒绝权限会导致 App 功能残缺，主流程无法继续，产生误报失败。

#### 识别信号（dump 中出现以下任意特征即视为权限弹窗）

```
系统原生权限弹窗：
  package 包含 "com.android.permissioncontroller" 或 "android"
  id 包含  "permission_allow" / "button_allow" / "button_allow_always"
  text 包含 "允许" / "始终允许" / "仅在使用时允许"

App 自定义隐私协议弹窗：
  text 包含 "同意" / "同意并继续" / "我知道了" / "接受" / "确认" / "隐私政策"
```

#### 处理步骤

```
1. dump 发现上述特征
2. 点击优先级：
     "勾选同意权限" > "仅在使用时允许"  >  "允许"  >  "同意"  >  "我知道了"
3. tap 后 dump 确认弹窗消失
4. 继续主流程
```

> 若 case 要求拒绝，点击"拒绝"/"取消"，并 `report note --level warning` 记录。

---

### 规则 B：弹窗遮挡 — 先清场再操作

当页面被任何弹窗、浮层、营销层遮挡时，**必须先关闭弹窗，不得在遮挡层上执行业务操作。**

#### 识别信号（以下任意条件触发）

| 信号 | 说明 |
|------|------|
| `dump` 返回 `returned` ≤ 5 | 元素异常少，疑似浮层遮挡 |
| 出现 `ivClose` / `close` / `cancel` / `dismiss` / `skip` 类 id | 典型关闭按钮 |
| 出现"稍后" / "关闭" / "取消" 文本 + 无业务元素 | 营销弹窗特征 |
| tap 后未跳转预期页面，且截图显示页面中央/底部有浮层 | 点击被弹窗拦截 |
| `find` 只能命中关闭按钮或遮罩，找不到业务元素 | 主内容被遮挡 |

#### 处理步骤

```
1. dump --screenshot         # 截图确认当前状态
2. 识别弹窗类型（权限 / 营销 / 推荐 / 系统提示）
3. 查找关闭元素，优先级：
     ivClose  >  close  >  cancel  >  dismiss  >  skip  >  "稍后"  >  "关闭"
4. tap 关闭
5. dump 确认主页面元素恢复（returned 恢复正常数量）
6. 继续主流程
```

#### 实战提示

- 首页首次 `dump` 只返回极少元素（≤ 5）→ 高概率是营销/引导弹层，优先查找并关闭
- 关键操作（加购、提交、支付等）前若出现推荐弹窗 → 识别后关闭，再继续主流程
- 权限弹窗出现时，**不要关闭，应同意**（见规则 A）

---

### 规则 C：元素找不到 — 最多重试 1 次，禁止死循环

```
第 1 次找不到
    ↓
    dump --screenshot  ← 截图 + 结构化元素一起获取，AI 视觉 + 结构双通道判断
    ↓
    结合截图判断原因：
    ├─ 截图显示弹窗/浮层遮挡     → 执行规则 B 清场，重试一次
    ├─ 截图显示页面仍在加载      → wait <目标元素> --timeout 5000，重试一次
    ├─ 截图显示进了错误页面      → back 回退，重新导航，重试一次
    ├─ dump 结构有候选但名称偏差 → find <模糊词> 查候选，确认 id/text 后重试一次
    └─ 截图中目标元素视觉可见
       但 dump 找不到（WebView）  → 直接从截图估算坐标，tap --xy 操作

第 2 次仍找不到
    ↓
    report note "元素 <xxx> 找不到" --level warning --screenshot
    ↓
    ├─ 可跳过 → report case-skip
    └─ 不可跳过 → report case-fail --summary "<失败原因>"

禁止第 3 次尝试同一动作
```

#### 截图辅助识别说明

`dump --screenshot` 同时返回结构化元素列表和截图路径，**两者配合使用**：

- **结构化元素** → 优先用于定位（`id` / `text` / `center`）
- **截图** → 当结构化找不到目标时，观察截图判断：
  - 目标按钮/文字是否真实存在于屏幕上
  - 是否有弹窗、遮挡、加载动画
  - 元素视觉位置 → 估算 `--xy` 坐标点击（适合 WebView / 图片化页面）

#### tap 定位 fallback 顺序

```
tap --id  →  tap --text  →  tap --xy（坐标优先取 dump center 字段；WebView 页面从截图估算）
```

若目标在屏幕外：先 `scroll` 滚动，再重新 `find`。

#### 死循环速查表

| 危险模式 | 正确做法 |
|---------|----------|
| `find` 失败 → 反复 `dump` + `find` | 最多重试 1 次，失败则 case-fail |
| `wait` 超时 → 重新 `wait` | 超时后 `dump --screenshot` 判断原因 |
| 弹窗出现 → 反复关闭但不推进 | 同意权限弹窗；营销弹窗关闭后继续主流程 |
| 跳转后继续找旧页面的元素 | `page info` 确认当前页，再决定操作 |

---

### 规则 D：每步操作前确认页面

每次 `tap` 导致页面跳转后、每次 `back` 后，先执行 `page info` 或 `dump` 确认当前页面，再继续下一步。（必须确认当前页面，避免操作错误页面）

---

### 规则 E：执行 case 时必须走报告生命周期（强制）

**当用户明确要求"执行 case"、"跑一下 XX 流程"、"测试 XX 功能"时，必须全程走报告生命周期管理，禁止裸执行。**

#### 强制流程

```
1. report start "<用例集名称>"          # 开启报告（若已有 active report 则直接用）
2. report case-start "<case 名称>"     # 开启 case
3. ... 执行各步骤 ...
4. report case-end --status passed|failed|skipped
5. report finalize                      # 完成报告
6. 判断报告服务状态（见下方）
```

#### finalize 后的服务判断

执行 `report serve` 后，根据返回值决定行为：

| 返回字段 | 值 | 行为 |
|----------|-----|------|
| `reused_existing_server` | `true` | 服务已在运行，直接返回 `url` 给用户 |
| `reused_existing_server` | `false` | 已启动新服务，返回 `url` 给用户 |

```
ad-cli report serve
→ 返回 { "url": "http://127.0.0.1:8765/<run>/index.html",
          "root_url": "http://127.0.0.1:8765/",
          "reused_existing_server": true/false }
→ 将 url 告知用户，可直接点击查看报告
```

> `root_url` 是用例集总览页（列出所有历史 run），`url` 是本次 run 的详情页。
> 无论服务是新启动还是复用，都必须把 `url` 返回给用户。

#### 例外情况

- 用户只是单步探索（"帮我看看当前页面"、"dump 一下"），**不需要**开启报告
- 已有 active report 时，跳过 `report start` 直接 `report case-start`

---

## L2 · 执行流程

### 完整工作流

```
report start <suite_name>
    ↓
device info                      # 确认设备连接
    ↓
app info <package>               # 确认 App 已安装
    ↓
app launch <package>             # 启动 App
    ↓
[处理启动后弹窗 — 见规则 A/B]    # 权限 / 隐私协议 / 营销弹窗
    ↓
report case-start <case_name>
    ↓
page info                        # 确认起始页面
    ↓
find / exists / wait             # 轻量定位
    ↓
dump [--screenshot]              # 信息不足时读取元素
    ↓
tap / input / scroll             # 执行操作
    ↓
wait / exists                    # 验证操作结果
    ↓
report case-end --status passed|failed|skipped
    ↓
report finalize
```

### 报告证据策略

**每一个业务操作步骤都必须保留截图证据。** `tap` / `input` 自动截图，其余关键节点需主动补截图。

| 命令 | 截图行为 | 证据等级 |
|------|---------|----------|
| `find` / `wait` / `exists` / `page info` | 不截图 | — |
| `tap` / `input` | **自动截图**（含点击聚焦点位叠加） | checkpoint |
| `dump --screenshot` | 手动触发截图 | checkpoint |
| `screenshot` | 手动截图 | checkpoint |
| `report note --screenshot` | 手动截图 + 备注 | checkpoint |

**以下节点必须主动截图留证（执行 `dump --screenshot` 或 `screenshot`）：**

- 启动 App 后进入首页（确认初始状态）
- 每次弹窗关闭后（确认主界面恢复）
- 每次页面跳转成功后（确认到达预期页面）
- 关键操作完成后（如提交、确认、支付等节点）
- 出现 error / warning / fallback 时
- case 结束前（记录最终状态）

> `tap` / `input` 已自动截图，无需在其后额外执行 `screenshot`。


### 控 token 策略

- 能用 `find` 就先用 `find`，不要无脑 `dump`
- 同一页面避免连续多次完整 `dump`
- `dump` 默认 compact 模式，避免长 JSON
- 页面切换后先 `page info`，再决定是否重新 `dump`
- 遇到 fuzzy 候选时补一次 `dump --screenshot`，不要多轮模糊猜测

---

## L3 · 命令参考

### 报告类

#### `report start <suite_name> [--output-dir <dir>]`
开启一份执行报告，产物输出到 `./report/<run-id>/`。

```bash
ad-cli report start "测试回归用例集"
```

产物：`index.html`（可视化报告）、`report.json`、`executions/`、`screenshots/`

HTML 报告：左侧 Cases → 中间 Timeline（业务步骤/执行步骤切换）→ 右侧 Viewer（播放/详情）。
播放器：纯黑 canvas + 底部渐变控制条 + 胶卷条 + 右下角聚焦点位角标。

#### `report status`
查看当前激活报告状态。

#### `report case-start <case_name> [--description <text>]`
开启 case。若上一个 case 仍在 running，自动标记为 unfinished 后开启新 case。

#### `report case-end [--status passed|failed|skipped] [--summary <text>]`
结束 case。快捷命令：`report case-pass` / `report case-fail` / `report case-skip`

#### `report note <title> [--content <text>] [--level info|warning|error] [--screenshot]`
写入 AI 观察备注，作为 execution 记录落盘。

```bash
ad-cli report note "发现首页疑似弹窗" --level warning
ad-cli report note "支付页留证" --screenshot
```

#### `report finalize [--force]`
收口报告，清除 active 状态。若有 running case 默认报错，`--force` 强制收口。

#### `report serve [report_dir] [--port <port>]`
启动本地预览服务。不传 `report_dir` 时自动选最新报告。返回 `url` 字段。

---

### 系统感知类

#### `device info`
获取设备信息（model / brand / android / resolution）。

> `DEVICE_DISCONNECTED` 也可能是执行环境无 ADB 权限，先在终端执行 `adb devices` 复核。

#### `page info`
获取当前 App 包名和 Activity 名。

---

### App 管理类

#### `app list`
列出所有可启动 App，取 `package` 字段作为包名。

#### `app info <package>`
查询安装状态、版本号、是否运行中。

#### `app launch <package>`
启动 App，等待页面稳定后返回。

#### `app stop <package>`
强制关闭 App。

#### `app install <apk_path>`
安装 APK，`APP_NOT_INSTALLED` 时使用。

---

### 页面感知类

#### `dump [--screenshot]`
获取当前页面 UI 元素。

- 默认 compact 模式：只含可交互 + 有文本元素
- compact 返回 0 个元素时自动切 full 模式并截图
- `--screenshot` 强制附带截图

返回字段：`mode` / `total_elements` / `returned` / `data[]`（含 `id` `text` `center` `bounds` `clickable`）

> `returned` ≤ 5 时高度怀疑弹窗遮挡，执行规则 B

#### `find <query>`
精确查找元素；找不到时返回模糊候选（`matched: "fuzzy"`）；完全找不到返回 `ELEMENT_NOT_FOUND`。

#### `screenshot [path]`
手动截图，保存到 `./screenshot/`。

---

### 操作类

#### `tap --id <id> | --text <text> | --xy <x> <y> [--reason <text>]`
点击元素，等待页面稳定后返回。定位优先级：`--id` > `--text` > `--xy`。

`--reason` 写入报告"点击解释"区域，便于复盘误触和 fallback 原因。

#### `input --id <id> | --text <text> --value <text>`
在输入框输入文字（自动先聚焦）。

#### `scroll --direction up|down|left|right`
滑动页面。

#### `back`
返回键，等待页面稳定后返回页面信息。

#### `keyevent <key>`
系统按键：`home` / `back` / `enter` / `del` / `menu`

---

### 断言类

#### `exists <query>`
判断元素是否存在，返回 `exists: true/false`。

#### `get-text <query>`
获取元素文本内容（读取动态数据如价格、数量）。

#### `wait <query> [--timeout <ms>]`
等待元素出现，默认 5000ms。超时返回 `TIMEOUT` 错误码。

---

### Error Code 一览

| code | 含义 | 建议处理 |
|------|------|---------|
| `DEVICE_DISCONNECTED` | 设备未连接 | 检查 USB / adb devices |
| `ELEMENT_NOT_FOUND` | 元素不存在 | 执行规则 C |
| `AMBIGUOUS_MATCH` | 多元素匹配 | 改用更精确的 id |
| `APP_NOT_INSTALLED` | App 未安装 | app install |
| `APP_NOT_RUNNING` | App 未在前台 | app launch |
| `TIMEOUT` | 等待超时 | dump --screenshot 确认状态 |
| `PERMISSION_DENIED` | ADB 权限不足 | 开启 USB 调试并授权 |

---

### 投屏类（mirror）

> 环境要求：项目根目录 `.venv`（Python >= 3.10）已安装 `av`、`adbutils`、`opencv-python`、`PySide6`。  
> scrcpy-client 已内嵌至 `src/subsystems/mirror/scrcpy/`，无需额外安装。  
> 运行时由 `main.py` 自动调用 `.venv/bin/python3 src/subsystems/mirror/scrcpy_server.py`，无需手动切换解释器。

#### `mirror [--mode window|web] [--serial <serial>] [--max-size <px>] [--max-fps <fps>] [--bitrate <bps>] [--port <port>] [--sharpen] [--record <name>]`

实时投屏 Android 设备。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | `window` | `window`=PySide6 本地窗口；`web`=浏览器 MJPEG 流 |
| `--serial` | 自动选第一台 | 多设备时指定序列号 |
| `--max-size` | `1024` | 最大分辨率（长边），越小越省带宽 |
| `--max-fps` | `60` | 最大帧率 |
| `--bitrate` | `2000000` | 视频码率 bps（默认 2 Mbps） |
| `--port` | `8888` | web 模式监听端口 |
| `--sharpen` | 关闭 | 开启画面锐化滤镜（window 模式有效） |
| `--record` | 无 | 录制操作并保存为 `<name>.json` |

**window 模式**（PySide6）

```bash
ad-cli mirror
ad-cli mirror --max-fps 30 --sharpen
```

- 无白边，支持拖拽缩放，自动等比居中（黑底 letterbox）
- 鼠标点击/拖拽实时映射到设备触控坐标
- 关闭窗口自动停止 scrcpy client

**web 模式**（MJPEG 浏览器流）

```bash
ad-cli mirror --mode web
ad-cli mirror --mode web --port 9000
```

- 自动打开浏览器 `http://localhost:<port>`
- 支持鼠标点击/拖拽触控映射（通过 `/touch?action=down|move|up&rx=&ry=` 接口）
- 支持移动端浏览器触控（touchstart / touchmove / touchend）
- Ctrl+C 退出

**停止后台投屏**

```bash
ad-cli mirror stop
```

**输出示例**

```json
{"status": "ok", "command": "mirror", "message": "投屏已启动 464×1024", "resolution": [464, 1024]}
```

---

### 回放类（replay）

#### `replay [name] [--recording] [--full] [--case <id>] [--speed <n>] [--dry-run] [--mirror]`

回放测试报告或录制文件。

| 参数 | 说明 |
|------|------|
| `name` | 报告目录名或录制文件名（省略则用最新报告） |
| `--recording` | 回放录制文件（`mirror --record` 产物）而非报告 |
| `--full` | 回放全部 case（含已跳过） |
| `--case <id>` | 只回放指定 case |
| `--speed <n>` | 回放速度倍率，默认 1.0 |
| `--dry-run` | 空跑模式，不实际执行 ADB 操作 |
| `--mirror` | 同步在后台启动 mirror web 投屏（端口 8889），方便同步观察 |

```bash
ad-cli replay                        # 回放最新报告
ad-cli replay 星巴克测试-20260518    # 回放指定报告
ad-cli replay --mirror               # 回放 + 同步投屏观察
ad-cli replay --dry-run              # 空跑验证步骤
```

---

### 缓存类（cache）

#### `cache stats`
查看元素坐标缓存统计（命中率、条目数等）。

#### `cache clear [--package <pkg>]`
清除缓存。不传 `--package` 时清除全部，传则只清指定 App。

#### `cache set-confidence <value>`
设置 pHash 缓存置信度阈值（0-100），影响坐标命中判断严格程度。
