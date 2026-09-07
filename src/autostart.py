"""开机自启：Windows 注册表 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run（无需管理员权限）"""
import os
import subprocess
import sys
import winreg

from config import APP_NAME

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClipboardHistory"


def _launch_command() -> str:
    """生成开机自启命令：
    - 打包后（PyInstaller）：exe 路径
    - 开发期：pythonw.exe + main.py（无控制台窗口）"""
    if getattr(sys, "frozen", False):
        # 打包后用 sys.executable（main.py 为打包入口时不带参数）
        return f'"{sys.executable}"'
    main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "main.py")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    py = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{py}" "{main_py}"'


def is_enabled() -> bool:
    """当前注册表中是否已启用开机自启。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def enable() -> bool:
    """写入开机自启注册表。返回是否成功。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        return True
    except OSError:
        return False


def disable() -> bool:
    """移除开机自启注册表项。返回是否成功（不存在也算成功）。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME, )
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()


def get_current_command() -> str | None:
    """读取当前注册表中的命令（仅用于校验展示）。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return value
    except OSError:
        return None
