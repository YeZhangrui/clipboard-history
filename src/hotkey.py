"""全局快捷键（Windows RegisterHotKey 窗口热键 + 消息过滤），支持两个角色：
- main ：主界面快捷键（唤出/最小化双向）          默认 Ctrl+Shift+V
- float：悬浮面板快捷键（显示/隐藏双向）          默认 Ctrl+Shift+F

组合预设可在设置中切换；被其他程序占用时注册失败自动禁用并提示。
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QWidget

MOD_ALT = 0x1
MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
WM_HOTKEY = 0x0312

_VK = {"C": 0x43, "V": 0x56, "X": 0x58, "F": 0x46, "E": 0x45}

# 角色：热键 ID + 预设 + 默认组合
ROLES = {
    "main": {
        "id": 0xC1B0,
        "default": "Ctrl+Shift+V",
        "presets": {
            "Ctrl+Shift+V": (MOD_CONTROL | MOD_SHIFT, _VK["V"]),
            "Ctrl+Alt+V": (MOD_CONTROL | MOD_ALT, _VK["V"]),
            "Ctrl+Shift+C": (MOD_CONTROL | MOD_SHIFT, _VK["C"]),
            "Ctrl+Alt+C": (MOD_CONTROL | MOD_ALT, _VK["C"]),
            "禁用": None,
        },
    },
    "float": {
        "id": 0xC1B1,
        "default": "Ctrl+Shift+F",
        "presets": {
            "Ctrl+Shift+F": (MOD_CONTROL | MOD_SHIFT, _VK["F"]),
            "Ctrl+Alt+F": (MOD_CONTROL | MOD_ALT, _VK["F"]),
            "Ctrl+Shift+E": (MOD_CONTROL | MOD_SHIFT, _VK["E"]),
            "Ctrl+Alt+E": (MOD_CONTROL | MOD_ALT, _VK["E"]),
            "禁用": None,
        },
    },
}

_user32 = ctypes.WinDLL("user32", use_last_error=True)


class HotkeyManager(QAbstractNativeEventFilter):
    """注册/注销全局热键（每个角色注册到隐藏宿主窗口）；WM_HOTKEY 按 wParam 路由回调。
    仅继承 QAbstractNativeEventFilter（QObject 多重继承会导致 PySide6 事件分派异常）。"""

    def __init__(self, app, callbacks: dict):
        """callbacks: {"main": fn, "float": fn}（任一角色 nil 亦可）。"""
        super().__init__()
        self._app = app
        self._callbacks = dict(callbacks)
        self._current = {}  # role -> 组合名（None=禁用）
        # 隐藏宿主窗口：热键捕获目标
        self._host = QWidget()
        self._host.hide()
        self._host.winId()
        app.installNativeEventFilter(self)

    # ---------- 对外 ----------

    def set_hotkey(self, role: str, name: str) -> bool:
        """切换某角色热键组合；'禁用' 返回 True；注册失败（占用/重复）返回 False。"""
        if role not in ROLES:
            return False
        self._unregister(role)
        preset = ROLES[role]["presets"].get(name)
        if preset is None:
            self._current[role] = None
            return True  # 已禁用
        # 与其他角色重复检查（同组合不能同时注册两次）
        for other, cur in self._current.items():
            if other != role and cur == name:
                self._current[role] = None
                return False
        mods, vk = preset
        hwnd = int(self._host.winId())
        ok = _user32.RegisterHotKey(hwnd, ROLES[role]["id"], mods, vk) != 0
        self._current[role] = name if ok else None
        return ok

    def apply_from_settings(self) -> bool:
        from config import load_settings
        settings = load_settings()
        ok_main = self.set_hotkey("main", settings.get("hotkey", ROLES["main"]["default"]))
        ok_float = self.set_hotkey("float", settings.get("hotkey_float", ROLES["float"]["default"]))
        return ok_main and ok_float

    def current_name(self, role: str) -> str:
        return self._current.get(role) or "禁用"

    def register_error_text(self) -> str:
        err = ctypes.get_last_error() or _user32.GetLastError()
        names = {1409: "该快捷键已被其他程序注册", 1400: "无效参数（组合不受支持）"}
        return names.get(err, f"注册失败（Win32 错误 {err}）")

    # ---------- 内部 ----------

    def _unregister(self, role: str):
        if self._current.get(role) is not None:
            _user32.UnregisterHotKey(int(self._host.winId()), ROLES[role]["id"])
        self._current[role] = None

    # ---------- 事件 ----------

    def nativeEventFilter(self, eventType, message):
        try:
            et = bytes(eventType)
        except TypeError:
            et = eventType
        if et in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                addr = int(message)
                if addr <= 0:
                    return False, 0
                msg = wintypes.MSG.from_address(addr)
                if msg.message == WM_HOTKEY:
                    cb = None
                    for role, cfg in ROLES.items():
                        if msg.wParam == cfg["id"]:
                            cb = self._callbacks.get(role)
                            break
                    if cb is not None:
                        cb()
                        return True, 0
            except (TypeError, ValueError, OSError):
                return False, 0
        return False, 0
