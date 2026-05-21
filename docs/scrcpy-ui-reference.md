# Py-Scrcpy-Client UI 模块参考文档

> 本文档面向需要在其他仓库中重新实现 scrcpy UI 客户端的开发者，涵盖依赖、核心 API、实现细节和入参说明。

---

## 一、依赖清单

### 运行时依赖

| 包名 | 版本约束 | 用途 |
|---|---|---|
| [`scrcpy-client`](pyproject.toml:2) | `0.4.7` (核心库) | ADB 通信、H.264 解码、控制指令注入 |
| `PySide6` | `>=6.0.0` | Qt6 Python 绑定，UI 框架 |
| `numpy` | `>=2` | 视频帧数组处理 |
| `av` (PyAV) | `>=12` | H.264 视频解码（FFmpeg 绑定） |
| `adbutils` | `>=2` | ADB 设备管理、Socket 通信 |
| `Python` | `>=3.9, <3.13` | 运行时版本 |

### 安装命令

```bash
pip install scrcpy-client[ui]
# 或分别安装：
pip install scrcpy-client PySide6 numpy av adbutils
```

---

## 二、架构总览

```
┌─────────────────────────────────────────────────┐
│                   UI 层 (你的实现)                 │
│  QMainWindow / QLabel / QComboBox / QPushButton  │
│        ↑ 监听 EVENT_FRAME       │ 调用 control.*    │
├─────────────────────────────────────────────────┤
│              scrcpy.Client (核心库)                │
│  ┌──────────────┐   ┌──────────────────────────┐ │
│  │ 视频流解码     │   │  ControlSender            │ │
│  │ H.264→ndarray │   │  touch/keycode/text/...  │ │
│  └──────┬───────┘   └───────────┬──────────────┘ │
├─────────┼───────────────────────┼─────────────────┤
│  ADB    │ video_socket          │ control_socket   │
├─────────┼───────────────────────┼─────────────────┤
│ Android │ scrcpy-server.jar (Java)                │
└─────────┴─────────────────────────────────────────┘
```

**设计模式**：观察者模式 — `Client` 通过 `add_listener` 注册回调，将 `EVENT_INIT` / `EVENT_FRAME` / `EVENT_DISCONNECT` 事件分发到 UI 层，实现核心库与 UI 完全解耦。

---

## 三、核心 API 参考

### 3.1 [`scrcpy.Client`](scrcpy/core.py:23) 构造函数

```python
from scrcpy import Client

client = Client(
    device: Optional[Union[AdbDevice, str]] = None,
    max_width: int = 0,
    bitrate: int = 8000000,
    max_fps: int = 0,
    flip: bool = False,
    block_frame: bool = False,
    stay_awake: bool = False,
    lock_screen_orientation: int = LOCK_SCREEN_ORIENTATION_UNLOCKED,
    connection_timeout: int = 3000,
    encoder_name: Optional[str] = None,
    codec_name: Optional[str] = None,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `device` | `AdbDevice \| str \| None` | `None` | Android 设备，`None` 时选择第一个，传 `str` 时按 serial 查找 |
| `max_width` | `int` | `0` | 视频帧宽度上限，`0` 表示不限 |
| `bitrate` | `int` | `8_000_000` | 视频码率 (bps)，UI 端用了 `1_000_000_000` (1Gbps) |
| `max_fps` | `int` | `0` | 最大帧率，`0` 表示不限（需 Android 10+） |
| `flip` | `bool` | `False` | 水平翻转画面 |
| `block_frame` | `bool` | `False` | 仅返回非空帧 |
| `stay_awake` | `bool` | `False` | 保持设备唤醒 |
| `lock_screen_orientation` | `int` | `-1` | 锁定屏幕方向，取值见下方常量 |
| `connection_timeout` | `int` | `3000` | 连接超时 (ms) |
| `encoder_name` | `str \| None` | `None` | 编码器名称：`OMX.google.h264.encoder` / `OMX.qcom.video.encoder.avc` / `c2.qti.avc.encoder` / `c2.android.avc.encoder` |
| `codec_name` | `str \| None` | `None` | 编码类型：`h264` / `h265` / `av1` |

### 3.2 可读写属性

| 属性 | 类型 | 说明 |
|---|---|---|
| `client.flip` | `bool` | 运行时切换翻转 |
| `client.device` | `AdbDevice` | 更换设备（需先 `stop()`） |
| `client.last_frame` | `np.ndarray \| None` | 最新视频帧 |
| `client.resolution` | `Tuple[int, int] \| None` | 设备分辨率 `(width, height)` |
| `client.device_name` | `str \| None` | 设备名称 |
| `client.control` | `ControlSender` | 控制指令发送器 |
| `client.alive` | `bool` | 运行状态 |

### 3.3 生命周期方法

```python
# 启动视频流（阻塞当前线程）
client.start()

# 启动视频流（在守护线程中运行，不阻塞）
client.start(daemon_threaded=True)

# 停止视频流、关闭所有 socket
client.stop()
```

### 3.4 事件监听

```python
client.add_listener(event_type: str, callback: Callable)
client.remove_listener(event_type: str, callback: Callable)
```

| 事件类型 | 常量 | 回调签名 | 说明 |
|---|---|---|---|
| `"init"` | `scrcpy.EVENT_INIT` | `callback()` | 连接初始化完成 |
| `"frame"` | `scrcpy.EVENT_FRAME` | `callback(frame: np.ndarray \| None)` | 视频帧到达，`None` 表示空帧（阻塞时跳过） |
| `"disconnect"` | `scrcpy.EVENT_DISCONNECT` | `callback()` | 连接断开 |

**帧格式**：`numpy.ndarray`，shape `(H, W, 3)`，`dtype=uint8`，颜色排序 **BGR24**。

### 3.5 ControlSender — 控制指令

所有方法通过 `client.control` 调用：

```python
# 按键
client.control.keycode(keycode: int, action: int, repeat: int = 0)

# 文本输入
client.control.text(text: str)

# 触摸
client.control.touch(x: int, y: int, action: int, touch_id: int = 0x1234567887654321)

# 滚动
client.control.scroll(x: int, y: int, h: int, v: int)

# 返回/亮屏
client.control.back_or_turn_screen_on(action: int)

# 通知/设置面板
client.control.expand_notification_panel()
client.control.expand_settings_panel()
client.control.collapse_panels()

# 剪贴板
client.control.get_clipboard()           # -> str
client.control.set_clipboard(text: str, paste: bool = False)

# 屏幕电源
client.control.set_screen_power_mode(mode: int)

# 旋转
client.control.rotate_device()

# 滑动
client.control.swipe(start_x, start_y, end_x, end_y, move_step_length=5, move_steps_delay=0.005)
```

### 3.6 动作常量 (action)

| 常量 | 值 | 说明 |
|---|---|---|
| `scrcpy.ACTION_DOWN` | `0` | 按下 |
| `scrcpy.ACTION_UP` | `1` | 抬起 |
| `scrcpy.ACTION_MOVE` | `2` | 移动 |

### 3.7 屏幕方向常量 (lock_screen_orientation)

| 常量 | 值 | 说明 |
|---|---|---|
| `LOCK_SCREEN_ORIENTATION_UNLOCKED` | `-1` | 不锁定 |
| `LOCK_SCREEN_ORIENTATION_INITIAL` | `-2` | 初始方向 |
| `LOCK_SCREEN_ORIENTATION_0` | `0` | 锁定 0° |
| `LOCK_SCREEN_ORIENTATION_1` | `1` | 锁定 90° |
| `LOCK_SCREEN_ORIENTATION_2` | `2` | 锁定 180° |
| `LOCK_SCREEN_ORIENTATION_3` | `3` | 锁定 270° |

### 3.8 常用按键常量 (部分)

| 常量 | 值 | 说明 |
|---|---|---|
| `KEYCODE_HOME` | `3` | 主页 |
| `KEYCODE_BACK` | `4` | 返回 |
| `KEYCODE_ENTER` | `66` | 回车 |
| `KEYCODE_DEL` | `67` | 删除 |
| `KEYCODE_SPACE` | `62` | 空格 |
| `KEYCODE_TAB` | `61` | Tab |
| `KEYCODE_SHIFT_LEFT` | `59` | 左 Shift |
| `KEYCODE_CTRL_LEFT` | `113` | 左 Ctrl |
| `KEYCODE_VOLUME_UP` | `24` | 音量+ |
| `KEYCODE_VOLUME_DOWN` | `25` | 音量- |
| `KEYCODE_POWER` | `26` | 电源 |

> 完整按键列表见 [`scrcpy/const.py`](scrcpy/const.py:10)，共约 290 个键码。

---

## 四、UI 实现详解

### 4.1 布局结构

使用 PySide6 实现以下三行式垂直布局：

```
┌─────────────────────────────────────────┐
│  [Spacer] Device: [QComboBox] [☐ Flip]  │  ← 顶部工具栏
├─────────────────────────────────────────┤
│                                         │
│           QLabel (视频画面)               │  ← 中部视频区 (stretch=100)
│                                         │
├─────────────────────────────────────────┤
│       [Spacer] [HOME] [BACK] [Spacer]    │  ← 底部按键栏
└─────────────────────────────────────────┘
```

参考 UI 控件的 `objectName`：

| 控件名 | 类型 | 用途 |
|---|---|---|
| `combo_device` | `QComboBox` | 设备选择下拉框 |
| `flip` | `QCheckBox` | 翻转画面开关 |
| `label` | `QLabel` | 视频帧渲染载体 |
| `button_home` | `QPushButton` | HOME 按键 |
| `button_back` | `QPushButton` | BACK 按键 |

### 4.2 初始化流程

```python
from adbutils import adb
from PySide6.QtWidgets import QApplication, QMainWindow
import scrcpy

class MainWindow(QMainWindow):
    def __init__(self, max_width: int, serial: str = None, encoder_name: str = None):
        super().__init__()
        self.max_width = max_width  # 窗口最大宽度，默认 800

        # 1. 获取 ADB 设备列表，填充下拉框
        items = [i.serial for i in adb.device_list()]
        self.ui.combo_device.addItems(items)

        # 2. 获取目标设备
        device = adb.device(serial=serial or items[0])

        # 3. 创建 Client
        self.client = scrcpy.Client(
            device=device,
            flip=False,
            bitrate=1000000000,    # 1Gbps 极高码率
            encoder_name=encoder_name,
            max_fps=60,
        )

        # 4. 注册事件监听
        self.client.add_listener(scrcpy.EVENT_INIT, self.on_init)
        self.client.add_listener(scrcpy.EVENT_FRAME, self.on_frame)

        # 5. 绑定 UI 控件事件 ... (见下文)

        # 6. 启动
        self.client.start(daemon_threaded=True)
```

### 4.3 视频帧渲染 (`on_frame`)

```python
from PySide6.QtGui import QImage, QPixmap

def on_init(self):
    self.setWindowTitle(f"Serial: {self.client.device_name}")

def on_frame(self, frame):
    QApplication.processEvents()  # 防止 UI 卡死
    if frame is None:
        return

    # frame: numpy.ndarray, shape (H, W, 3), dtype uint8, BGR24
    image = QImage(
        frame,                        # 帧数据
        frame.shape[1],               # 宽度
        frame.shape[0],               # 高度
        frame.shape[1] * 3,           # 每行字节数 (bytesPerLine)
        QImage.Format_BGR888,         # 颜色格式
    )
    pix = QPixmap(image)

    # 缩放适配窗口
    ratio = self.max_width / max(self.client.resolution)
    pix.setDevicePixelRatio(1 / ratio)

    self.ui.label.setPixmap(pix)
    self.resize(1, 1)  # 触发自动调整窗口大小
```

**关键点**：
- 帧格式是 **BGR888**，不是 RGB；每行字节数 = `width * 3`
- `setDevicePixelRatio` 用于缩放而非直接 `QPixmap.scaled()`，保持高 DPI 清晰度
- `self.resize(1, 1)` 是技巧性调用，触发 Qt 根据 label 内容自动调整窗口大小

### 4.4 鼠标触摸事件

直接在 `QLabel` 上覆写鼠标事件处理函数：

```python
from PySide6.QtGui import QMouseEvent

def make_mouse_handler(self, action):
    def handler(evt: QMouseEvent):
        # 清除焦点（避免键盘被 widget 拦截）
        focused = QApplication.focusWidget()
        if focused:
            focused.clearFocus()

        # 坐标映射：Qt 窗口坐标 → 设备真实坐标
        ratio = self.max_width / max(self.client.resolution)
        x = evt.position().x() / ratio
        y = evt.position().y() / ratio

        self.client.control.touch(x, y, action)
    return handler

# 绑定
self.ui.label.mousePressEvent   = self.make_mouse_handler(scrcpy.ACTION_DOWN)
self.ui.label.mouseMoveEvent    = self.make_mouse_handler(scrcpy.ACTION_MOVE)
self.ui.label.mouseReleaseEvent = self.make_mouse_handler(scrcpy.ACTION_UP)
```

**坐标映射公式**：
```
device_x = qt_x / ratio
device_y = qt_y / ratio
其中 ratio = max_width / max(device_width, device_height)
```

### 4.5 键盘事件

直接在 `QMainWindow` 上覆写 `keyPressEvent` / `keyReleaseEvent`：

```python
from PySide6.QtGui import QKeyEvent

def make_key_handler(self, action):
    def handler(evt: QKeyEvent):
        code = self.map_qt_to_android(evt.key())
        if code != -1:
            self.client.control.keycode(code, action)
    return handler

self.keyPressEvent   = self.make_key_handler(scrcpy.ACTION_DOWN)
self.keyReleaseEvent = self.make_key_handler(scrcpy.ACTION_UP)
```

**Qt → Android 键码映射规则**：

| Qt 键码范围 | Android 键码 | 映射公式 |
|---|---|---|
| `48 ~ 57` (数字 0-9) | `7 ~ 16` (KEYCODE_0~9) | `android = qt - 48 + 7` |
| `65 ~ 90` (大写 A-Z) | `29 ~ 54` (KEYCODE_A~Z) | `android = qt - 65 + 29` |
| `97 ~ 122` (小写 a-z) | `29 ~ 54` (KEYCODE_A~Z) | `android = qt - 97 + 29` |
| `32` (Space) | `62` (KEYCODE_SPACE) | 硬编码 |
| `16777219` (Del) | `67` (KEYCODE_DEL) | 硬编码 |
| `16777220` (Enter) | `66` (KEYCODE_ENTER) | 硬编码 |
| `16777217` (Tab) | `61` (KEYCODE_TAB) | 硬编码 |
| `16777248` (Shift) | `59` (KEYCODE_SHIFT_LEFT) | 硬编码 |
| `16777249` (Ctrl) | `113` (KEYCODE_CTRL_LEFT) | 硬编码 |
| 其他 | `-1` (忽略) | — |

### 4.6 设备切换

```python
def choose_device(self, serial: str):
    # 验证设备存在
    if serial not in [i.serial for i in adb.device_list()]:
        QMessageBox.warning(self, "Error", f"Device [{serial}] not found!")
        return

    self.ui.combo_device.setCurrentText(serial)

    # 热切换设备
    if hasattr(self, "client"):
        self.client.stop()                           # 停止当前连接
        self.client.device = adb.device(serial=serial)  # 更换设备
        self.client.start()                          # 重新启动
```

### 4.7 关闭处理

```python
def closeEvent(self, event):
    self.client.stop()
    self.alive = False
```

### 4.8 CLI 入口

```python
from argparse import ArgumentParser

def main():
    parser = ArgumentParser(description="A simple scrcpy client")
    parser.add_argument("-m", "--max_width", type=int, default=800,
                        help="Set max width of the window, default 800")
    parser.add_argument("-d", "--device", type=str,
                        help="Select device manually (device serial required)")
    parser.add_argument("--encoder_name", type=str,
                        help="Encoder name to use")
    args = parser.parse_args()

    app = QApplication([])
    m = MainWindow(args.max_width, args.device, args.encoder_name)
    m.show()
    app.exec()
```

---

## 五、在其他仓库中使用 `scrcpy` 核心库（无 UI）

如果你需要在其他项目中复用核心库而不带 PySide6，只需安装核心依赖：

```bash
pip install scrcpy-client        # 不装 ui extra
# 或
pip install av numpy adbutils scrcpy-client
```

### 最小示例

```python
import cv2
import scrcpy
from adbutils import adb

client = scrcpy.Client(device=adb.device_list()[0])

def on_frame(frame):
    if frame is not None:
        # frame: numpy.ndarray, BGR24, 可直接用于 OpenCV
        cv2.imshow("scrcpy", frame)
        cv2.waitKey(1)

client.add_listener(scrcpy.EVENT_FRAME, on_frame)
client.start()  # 阻塞
```

---

## 六、注意事项 & 已知问题

1. **BGR 而非 RGB**：[`on_frame`](scrcpy_ui/main.py:154) 使用 `QImage.Format_BGR888`，视频帧是 BGR 像素排列，直接用于 OpenCV 是正确的。

2. **`main()` 循环 bug**：[`main()`](scrcpy_ui/main.py:192) 中 `while m.alive: m.client.start()` 无法工作，因为 `start()` 内部有 `assert self.alive is False`，第二次调用会抛出 `AssertionError`。正确做法是使用 `daemon_threaded=True` 启动 + `app.exec()` 事件循环。

3. **坐标映射**：`ratio` 计算基于 `max_width` 和设备分辨率的最大边，窗口调整大小时触摸坐标映射可能失准。

4. **屏幕方向**：横屏设备的 `resolution` 仍然是竖屏尺寸，需要额外处理旋转。

5. **多指触控**：`touch_id` 参数支持，但当前 UI 未实现。

6. **ADB 环境**：确保 `adb` 在 PATH 中，且设备已通过 USB/WiFi 授权连接。