# ad-cli 安装指南

一键安装脚本适配 macOS、Linux 和 Windows。

## 快速开始

### macOS / Linux
```bash
bash install.sh
```

安装完成后重开终端（或执行 `source ~/.zshrc`），即可使用：

```bash
ad-cli --help
ad-cli device info
```

### Windows
```bat
install.bat
```

重新打开终端后使用：

```bat
ad-cli --help
ad-cli device info
```

---

## 安装内容

| 步骤 | 说明 |
|------|------|
| Python 虚拟环境 | 创建 `.venv`（Python >= 3.10） |
| 基础依赖 | `Pillow`、`argcomplete` |
| 投屏依赖（可选） | `av`、`adbutils`、`opencv-python`、`numpy`、`PySide6` |
| `ad-cli` 命令 | 写入 `~/.local/bin/`（macOS/Linux）或 `%LOCALAPPDATA%\Programs\ad-cli\`（Windows） |
| Tab 补全 | 写入 `~/.zshrc` / `~/.bashrc`（macOS/Linux）或 PowerShell `$PROFILE`（Windows） |

安装脚本会询问是否安装投屏依赖：

```
是否安装投屏依赖（PySide6 / opencv / scrcpy-client）？[Y/n]
```

选 `Y` 安装（支持 `ad-cli mirror`），选 `n` 跳过（仅保留 CLI 功能）。

> scrcpy-client 已内嵌至 `src/subsystems/mirror/scrcpy/`，无需 pip 安装。

---

## 环境要求

| 组件 | 要求 | 说明 |
|------|------|------|
| Python | >= 3.10 | 安装脚本自动查找 |
| adb | 推荐安装 | 连接 Android 设备必须，`brew install android-platform-tools` |
| PySide6 | 投屏可选 | `mirror --mode window` GUI 模式需要 |

---

## Tab 补全

安装脚本自动注册 shell 补全，重开终端后生效：

| Shell | 支持 | 方式 |
|-------|------|------|
| zsh / bash | ✅ | 自动写入 `~/.zshrc` / `~/.bashrc` |
| PowerShell | ✅ | 自动写入 `$PROFILE` |
| cmd.exe | ❌ | 可安装 [Clink](https://chrisant996.github.io/clink/) 后重跑 `install.bat` 获得支持 |

---

## 故障排查

| 问题 | 解决 |
|------|------|
| `ad-cli: command not found` | 重新打开终端；或检查 `~/.local/bin` 是否在 PATH |
| Tab 补全不生效 | 执行 `source ~/.zshrc`（当前终端），或重开终端 |
| `adb: not found` | macOS: `brew install android-platform-tools` |
| 设备未识别 | 检查 USB 调试是否开启，执行 `adb devices` 确认 |
| 投屏依赖安装失败 | 重新运行安装脚本选 Y，或手动执行 `.venv/bin/pip install av adbutils opencv-python numpy PySide6` |

---

## 卸载

**macOS / Linux**
```bash
# 删除命令
rm ~/.local/bin/ad-cli

# 删除 Tab 补全（从 ~/.zshrc 或 ~/.bashrc 中移除含 register-python-argcomplete 的行）

# 删除运行时数据
rm -rf ~/.ad-cli

# 删除虚拟环境
rm -rf /path/to/ad-cli/.venv
```

**Windows**
```bat
REM 删除命令目录
rmdir /s %LOCALAPPDATA%\Programs\ad-cli

REM 从用户 PATH 中移除该目录（系统设置 → 高级 → 环境变量）

REM 删除运行时数据
rmdir /s %USERPROFILE%\.ad-cli
```

---

## 开发者

从源码安装：

```bash
pip install -e .            # 仅 CLI
pip install -e ".[mirror]"  # 含投屏依赖
pip install -e ".[all]"     # 全部
```
