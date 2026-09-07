"""主题管理：浅色 / 深色 / 跟随系统（Windows）三模式，运行时热切换。"""
import winreg

from PySide6.QtCore import QObject, QTimer, Signal

from config import load_settings, save_settings
from ui.style import DARK_TOKENS, LIGHT_TOKENS, build_stylesheet

DEFAULT_MODE = "system"   # 默认跟随系统
SYSTEM_POLL_MS = 2000     # 跟随系统模式下轮询注册表周期

_PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

# 当前生效的色板（ThemeManager.apply 时更新；供卡片阴影等实时读取）
_CURRENT_TOKENS = LIGHT_TOKENS


def get_tokens() -> dict:
    """当前生效的色板 token（浅色/深色）。"""
    return _CURRENT_TOKENS


def system_dark() -> bool:
    """读取 Windows 应用主题：AppsUseLightTheme=0 → 深色。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except OSError:
        return False


def get_mode_from_settings() -> str:
    mode = load_settings().get("theme", DEFAULT_MODE)
    return mode if mode in ("light", "dark", "system") else DEFAULT_MODE


def effective_theme() -> str:
    """当前实际生效的主题（"跟随系统"时按系统主题解析）。"""
    mode = get_mode_from_settings()
    if mode == "system":
        return "dark" if system_dark() else "light"
    return mode


class ThemeManager(QObject):
    """应用级主题：resolve(模式) → 生成 QSS 应用到 app；跟随系统时轮询同步。"""

    theme_changed = Signal(str)  # "light" | "dark"

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._mode = get_mode_from_settings()
        self._current = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_system)
        self._timer.start(SYSTEM_POLL_MS)

    # ---------- 对外 ----------

    def get_mode(self) -> str:
        return self._mode

    def resolve(self) -> str:
        if self._mode == "system":
            return "dark" if system_dark() else "light"
        return self._mode

    def apply(self):
        theme = self.resolve()
        if theme != self._current:
            self._current = theme
            global _CURRENT_TOKENS
            _CURRENT_TOKENS = DARK_TOKENS if theme == "dark" else LIGHT_TOKENS
            self._app.setStyleSheet(build_stylesheet(_CURRENT_TOKENS))
            self.theme_changed.emit(theme)

    def set_mode(self, mode: str):
        """用户切换主题：保存设置并立即应用。"""
        if mode not in ("light", "dark", "system"):
            return
        self._mode = mode
        settings = load_settings()
        settings["theme"] = mode
        save_settings(settings)
        self.apply()

    def current_tokens(self) -> dict:
        return DARK_TOKENS if self._current == "dark" else LIGHT_TOKENS

    def current_primary(self) -> str:
        return self.current_tokens()["primary"]

    def current_shadow_alpha(self) -> int:
        return self.current_tokens()["shadow_alpha"]

    # ---------- 内部 ----------

    def _poll_system(self):
        """跟随系统：每 2 秒检查系统主题变化，变化即热切换。"""
        if self._mode == "system":
            self.apply()
