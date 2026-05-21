@echo off
REM ============================================================
REM  ad-cli 安装脚本 (Windows)
REM  用法: 双击运行，或在 cmd 中执行 install.bat
REM ============================================================

setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%.venv

echo ==========================================
echo   ad-cli 安装程序 (Windows)
echo ==========================================

REM ── 1. 检查 Python ────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    echo         下载地址: https://www.python.org/downloads/
    echo         安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER%

REM 检查版本 >= 3.10
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo [ERROR] 需要 Python ^>= 3.10，当前版本: %PYVER%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo [ERROR] 需要 Python ^>= 3.10，当前版本: %PYVER%
    pause
    exit /b 1
)

REM ── 2. 创建虚拟环境 ───────────────────────────────────────
if not exist "%VENV_DIR%" (
    echo [-] 创建虚拟环境: %VENV_DIR%
    python -m venv "%VENV_DIR%"
) else (
    echo [-] 虚拟环境已存在: %VENV_DIR%
)

set PIP=%VENV_DIR%\Scripts\pip.exe
set VENV_PY=%VENV_DIR%\Scripts\python.exe

REM ── 3. 安装基础依赖 ───────────────────────────────────────
echo [-] 升级 pip / setuptools...
"%PIP%" install --upgrade pip setuptools -q
echo [-] 安装基础依赖...
"%PIP%" install -q Pillow

REM ── 4. 安装投屏依赖（可选）───────────────────────────────
echo.
set /p MIRROR_ANS=是否安装投屏依赖（PySide6 / opencv / scrcpy-client）？[Y/n] 
if /i "!MIRROR_ANS!"=="" set MIRROR_ANS=Y
if /i "!MIRROR_ANS!"=="Y" (
    echo [-] 安装投屏依赖...
    REM scrcpy-client 已内嵌至 src/subsystems/mirror/scrcpy/
    "%PIP%" uninstall -y scrcpy-client >nul 2>&1
    "%PIP%" install -q "av>=12,<13" "adbutils>=2,<3" ^
                      "opencv-python>=4.8.0" "numpy>=2,<3" "PySide6>=6.4.0"
    if errorlevel 1 (
        echo [ERR] 投屏依赖安装失败
    ) else (
        echo [OK] 投屏依赖安装完成
    )
)

REM ── 5. 安装 ad-cli 包 ─────────────────────────────────────
echo [-] 安装 ad-cli 命令...
"%PIP%" install -q argcomplete
"%PIP%" install -q -e "%SCRIPT_DIR%"

REM ── 6. 创建 wrapper 脚本 ─────────────────────────────────
set WRAPPER=%USERPROFILE%\AppData\Local\Programs\ad-cli
if not exist "%WRAPPER%" mkdir "%WRAPPER%"

REM cmd.exe 用 .bat wrapper
echo @echo off > "%WRAPPER%\ad-cli.bat"
echo "%VENV_PY%" -m ad_cli.main %%* >> "%WRAPPER%\ad-cli.bat"

REM PowerShell 用 .ps1 wrapper（argcomplete 需要直接调用 python）
echo param([Parameter(ValueFromRemainingArguments)]$args) > "%WRAPPER%\ad-cli.ps1"
echo ^& "%VENV_PY%" -m ad_cli.main @args >> "%WRAPPER%\ad-cli.ps1"

REM 将 wrapper 加入 PATH（当前用户，永久生效）
set "CURR_PATH="
for /f "tokens=2*" %%a in ('reg query HKCU\Environment /v PATH 2^>nul') do set CURR_PATH=%%b
echo !CURR_PATH! | find /i "%WRAPPER%" >nul 2>&1
if errorlevel 1 (
    if "!CURR_PATH!"=="" (
        setx PATH "%WRAPPER%" >nul
    ) else (
        setx PATH "!CURR_PATH!;%WRAPPER%" >nul
    )
    echo [OK] 已将 %WRAPPER% 添加到用户 PATH
)

echo.
echo ==========================================
echo [OK] 安装完成！
echo ==========================================
echo.
echo   命令: ad-cli
echo   位置: %WRAPPER%\ad-cli.bat
echo.
echo   注意: 需要重新打开终端才能使用 ad-cli 命令
echo.

REM ── 7. Tab 补全 ──────────────────────────────────────────
set REGISTER_AC=%VENV_DIR%\Scripts\register-python-argcomplete.exe

REM ── 7a. PowerShell 补全 ───────────────────────────────────
if exist "%REGISTER_AC%" (
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "echo $PROFILE"`) do set PS_PROFILE=%%p
    powershell -NoProfile -Command "if (Test-Path '%PS_PROFILE%') { if ((Get-Content '%PS_PROFILE%' -Raw) -match 'ad-cli') { exit 0 } else { exit 1 } } else { exit 1 }" >nul 2>&1
    if errorlevel 1 (
        for %%d in ("%PS_PROFILE%") do if not exist "%%~dpd" mkdir "%%~dpd"
        powershell -NoProfile -Command ^
            "$line = \"`n# ad-cli Tab 补全`n\$(\"%REGISTER_AC%\" --shell powershell ad-cli)\"; ^
             Add-Content -Path '%PS_PROFILE%' -Value \$line -Encoding UTF8"
        echo [OK] PowerShell Tab 补全已写入 %PS_PROFILE%
    ) else (
        echo [-] PowerShell Tab 补全已注册，跳过
    )
)

REM ── 7b. cmd.exe 补全（通过 Clink）────────────────────────
REM Clink 是 cmd.exe 的 readline 增强工具，支持 Lua 自定义补全
REM 下载: https://chrisant996.github.io/clink/
set CLINK_SCRIPTS=""
for /f "usebackq delims=" %%d in (`clink info 2^>nul ^| findstr /i "scripts"`) do (
    for /f "tokens=2*" %%a in ("%%d") do set CLINK_SCRIPTS=%%b
)
if not "%CLINK_SCRIPTS%"=="" (
    REM Clink 已安装，生成 Lua 补全脚本
    set LUA_FILE=%CLINK_SCRIPTS%\ad-cli.lua
    (
        echo -- ad-cli Tab 补全脚本（由 install.bat 自动生成）
        echo -- 依赖: Clink ^>= 1.x  https://chrisant996.github.io/clink/
        echo.
        echo local SUBCOMMANDS = {
        echo     "device", "page", "app", "report", "dump", "find",
        echo     "screenshot", "exists", "get-text", "wait",
        echo     "tap", "input", "scroll", "back", "keyevent",
        echo     "mirror", "replay", "cache",
        echo }
        echo.
        echo local SUBCOMMAND_ARGS = {
        echo     ["device"]     = { "info" },
        echo     ["page"]       = { "info" },
        echo     ["app"]        = { "list", "info", "launch", "stop", "install" },
        echo     ["report"]     = { "start", "status", "case-start", "case-end",
        echo                        "case-pass", "case-fail", "case-skip",
        echo                        "note", "finalize", "serve", "stop" },
        echo     ["mirror"]     = { "stop", "--mode", "--max-fps", "--max-size",
        echo                        "--bitrate", "--port", "--sharpen", "--record" },
        echo     ["tap"]        = { "--id", "--text", "--xy", "--label", "--reason" },
        echo     ["input"]      = { "--id", "--text", "--value" },
        echo     ["scroll"]     = { "--direction" },
        echo     ["dump"]       = { "--screenshot" },
        echo     ["wait"]       = { "--timeout" },
        echo     ["replay"]     = { "--recording", "--full", "--case",
        echo                        "--generate-report", "--speed", "--dry-run", "--mirror" },
        echo     ["cache"]      = { "stats", "clear", "set-confidence", "--package" },
        echo }
        echo.
        echo local function ad_cli_generator^(word, word_index, line_state^)
        echo     if word_index == 2 then
        echo         return SUBCOMMANDS
        echo     end
        echo     local subcmd = line_state:getword^(2^)
        echo     if subcmd and SUBCOMMAND_ARGS[subcmd] then
        echo         return SUBCOMMAND_ARGS[subcmd]
        echo     end
        echo end
        echo.
        echo clink.argmatcher^("ad-cli"^):addarg^(ad_cli_generator^)
    ) > "!LUA_FILE!"
    echo [OK] cmd.exe ^(Clink^) Tab 补全脚本已写入:
    echo      !LUA_FILE!
    echo      重新打开 cmd 窗口后生效
) else (
    echo [-] cmd.exe Tab 补全: 未检测到 Clink
    echo     安装 Clink 后可获得 Tab 补全支持:
    echo     https://chrisant996.github.io/clink/
)
echo.
echo.
echo   快速测试:
echo      ad-cli --help
echo      ad-cli device
echo.

REM ── 7. 检查 ADB ───────────────────────────────────────────
where adb >nul 2>&1
if errorlevel 1 (
    echo [WARN] 未检测到 adb，请安装 Android Platform Tools:
    echo        https://developer.android.com/tools/releases/platform-tools
    echo        下载后将目录添加到 PATH
)

echo.
pause
