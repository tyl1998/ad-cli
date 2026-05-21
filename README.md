# ad-cli

> Android 自动化 CLI — ADB 感知 / 操作 / 报告 / 投屏

通过命令行驱动 Android 设备，输出结构化 JSON，专为 AI Agent 工作流设计。

---

## 特性

- **感知**：dump UI 树、查找元素、截图、等待元素出现
- **操作**：tap / input / scroll / back / keyevent，操作后自动截图留证
- **报告**：完整测试生命周期管理，生成可视化 HTML 报告
- **投屏**：实时投屏到本地窗口（PySide6）或浏览器（MJPEG），支持触控映射
- **缓存**：pHash 坐标缓存，重复操作自动命中，加速执行
- **Tab 补全**：zsh / bash / PowerShell 全支持

---

## 安装

```bash
# macOS / Linux
bash install.sh

# Windows
install.bat
```

安装后重开终端即可使用，详见 [INSTALL.md](INSTALL.md)。

---

## 快速上手

```bash
# 查看所有命令
ad-cli --help

# 查看连接设备
ad-cli device info

# 获取当前页面 UI 元素
ad-cli dump

# 点击元素
ad-cli tap --text "登录"

# 截图
ad-cli screenshot

# 实时投屏
ad-cli mirror
```

---

## 测试报告

```bash
# 开启报告
ad-cli report start "功能回归"

# 执行 case
ad-cli report case-start "登录流程"
ad-cli app launch com.example.app
ad-cli tap --text "登录"
ad-cli report case-end --status passed

# 完成并预览
ad-cli report finalize
ad-cli report serve
# → 浏览器打开 http://127.0.0.1:8765/
```

---

## 投屏

```bash
# 本地窗口（默认）
ad-cli mirror

# 浏览器 MJPEG 流
ad-cli mirror --mode web --port 8888

# 停止后台投屏
ad-cli mirror stop
```

---

## 命令速查

| 命令 | 说明 |
|------|------|
| `device info` | 设备信息 |
| `page info` | 当前 App 包名 / Activity |
| `app list/launch/stop` | App 管理 |
| `dump [--screenshot]` | 获取 UI 元素 |
| `find <query>` | 查找元素 |
| `tap --id/--text/--xy` | 点击元素 |
| `input --id/--text --value` | 输入文字 |
| `scroll --direction` | 滑动页面 |
| `exists/wait <query>` | 断言 / 等待 |
| `report start/case-start/...` | 报告生命周期 |
| `mirror [--mode web]` | 实时投屏 |
| `replay [name]` | 回放报告 |
| `cache stats/clear` | 缓存管理 |

完整文档见 [.codex/skills/ad-cli-run/SKILL.MD](.codex/skills/ad-cli-run/SKILL.MD)。

---

## 环境要求

- Python >= 3.10
- adb（`brew install android-platform-tools`）
- 投屏功能额外需要：`PySide6`、`opencv-python`、`av`（安装时选 Y）

---

## 项目结构

```
ad-cli/
├── src/
│   ├── main.py              # CLI 入口路由
│   ├── commands/            # 各命令实现
│   │   ├── perception.py    # dump / find / screenshot / wait
│   │   ├── action.py        # tap / input / scroll / back
│   │   ├── app.py           # app 管理
│   │   ├── system.py        # device / page
│   │   └── report_cmd.py    # 报告生命周期
│   ├── core/                # ADB 底层封装、UI 解析
│   ├── cache/               # pHash 坐标缓存
│   ├── report/              # 报告生成 / HTML 渲染
│   └── subsystems/
│       └── mirror/          # 投屏模块（scrcpy + PySide6/MJPEG）
├── install.sh               # macOS / Linux 安装脚本
├── install.bat              # Windows 安装脚本
├── INSTALL.md               # 安装详细说明
└── pyproject.toml
```
