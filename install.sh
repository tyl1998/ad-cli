#!/bin/bash
# ============================================================
# ad-cli 安装脚本 (macOS / Linux)
# 用法: bash install.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_MIN="3.10"

echo "=========================================="
echo "  ad-cli 安装程序"
echo "=========================================="

# ── 1. 检查 Python 版本 ──────────────────────────────────────
find_python() {
    for cmd in python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python || true)
if [ -z "$PYTHON" ]; then
    echo "❌ 需要 Python >= $PYTHON_MIN"
    echo "   macOS 安装建议: brew install python@3.11"
    echo "   或使用 pyenv: pyenv install 3.11.9"
    exit 1
fi
echo "✅ Python: $($PYTHON --version)  ($PYTHON)"

# ── 2. 创建虚拟环境 ──────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "→ 创建虚拟环境: $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "→ 虚拟环境已存在: $VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
VENV_PY="$VENV_DIR/bin/python3"

# ── 3. 安装基础依赖 ──────────────────────────────────────────
echo "→ 升级 pip / setuptools（需要 >= 64 才支持 pyproject.toml editable）..."
"$PIP" install --upgrade pip setuptools -q
echo "→ 安装基础依赖..."
"$PIP" install -q Pillow

# ── 4. 安装投屏依赖（可选）──────────────────────────────────
echo ""
read -p "是否安装投屏依赖（PySide6 / opencv / scrcpy-client）？[Y/n] " ans
ans=${ans:-Y}
if [[ "$ans" =~ ^[Yy] ]]; then
    echo "→ 安装投屏依赖..."

    # scrcpy-client 已内嵌在 src/subsystems/mirror/scrcpy/，只需安装运行时依赖
    # 清理旧版 scrcpy-client（如果曾经通过 pip 装过）
    "$PIP" uninstall -y scrcpy-client 2>/dev/null || true

    "$PIP" install -q \
        "av>=12,<13" "adbutils>=2,<3" \
        "opencv-python>=4.8.0" "numpy>=2,<3" "PySide6>=6.4.0" || {
        echo "⚠️  投屏依赖安装失败"
        echo "   请尝试: $PIP install -r requirements.txt"
        exit 1
    }
    echo "✅ 投屏依赖安装完成"
fi

# ── 5. 安装 ad-cli 到系统 PATH ──────────────────────────────
echo "→ 安装 ad-cli 命令..."
"$PIP" install -q argcomplete

# 方案 A：pip install -e .（推荐，可随时更新）
"$PIP" install -q -e "$SCRIPT_DIR"

# 生成 wrapper 脚本（确保用正确的 venv python）
BIN_DIR=""
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    BIN_DIR="/usr/local/bin"
elif [ -d "$HOME/.local/bin" ]; then
    BIN_DIR="$HOME/.local/bin"
else
    mkdir -p "$HOME/.local/bin"
    BIN_DIR="$HOME/.local/bin"
fi

cat > "$BIN_DIR/ad-cli" << EOF
#!/bin/bash
exec "$VENV_DIR/bin/python3" -m ad_cli.main "\$@"
EOF
chmod +x "$BIN_DIR/ad-cli"

# ── 6. 注册 shell 补全 ───────────────────────────────────────
if [ -f "$VENV_DIR/bin/register-python-argcomplete" ]; then
    COMPLETION_SCRIPT="$VENV_DIR/bin/register-python-argcomplete"
    SHELL_RC=""
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_RC="$HOME/.bashrc"
    fi
    if [ -n "$SHELL_RC" ]; then
        COMPLETION_LINE="eval \"\$($VENV_DIR/bin/register-python-argcomplete ad-cli)\""
        if ! grep -qF 'register-python-argcomplete ad-cli' "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# ad-cli shell 补全" >> "$SHELL_RC"
            echo "$COMPLETION_LINE" >> "$SHELL_RC"
            echo "✅ Tab 补全已写入 $SHELL_RC"
            echo "   → 新开终端自动生效；当前终端执行一次: source $SHELL_RC"
            NEED_SOURCE="$SHELL_RC"
        else
            echo "→ Tab 补全已注册（新开终端自动生效），跳过"
        fi
    fi
fi

echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo "=========================================="
echo ""
echo "  命令: ad-cli"
echo "  位置: $BIN_DIR/ad-cli"
echo ""
if [ -n "${NEED_SOURCE:-}" ]; then
    echo "  ⚡ 当前终端执行一次即可激活 Tab 补全:"
    echo "       source $NEED_SOURCE"
    echo "  （新开终端无需此步骤，自动生效）"
    echo ""
fi

# 检查 PATH
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo "⚠️  请将以下内容加入 ~/.zshrc 或 ~/.bashrc："
    echo "     export PATH=\"$BIN_DIR:\$PATH\""
    echo ""
fi

echo "  快速测试:"
echo "     ad-cli --help"
echo "     ad-cli device"
echo "     ad-cli mirror"
echo ""

# ── 6. 检查 ADB ──────────────────────────────────────────────
if ! command -v adb &>/dev/null; then
    echo "⚠️  未检测到 adb，建议安装 Android Platform Tools："
    echo "   macOS: brew install android-platform-tools"
    echo "   或下载: https://developer.android.com/tools/releases/platform-tools"
fi
