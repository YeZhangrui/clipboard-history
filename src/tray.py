"""系统托盘：图标 + 菜单（打开主窗口 / 开机自启开关 / 退出）+ 气泡提示"""
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

import autostart
from config import APP_NAME, update_settings
from ui.style import make_app_icon


class TrayManager(QObject):
    def __init__(self, app, window, settings, parent=None):
        super().__init__(parent)
        self._app = app
        self._window = window
        self._settings = settings

        self.tray = QSystemTrayIcon(make_app_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} — 已开启剪贴板历史记录")

        menu = QMenu()
        self.open_action = QAction("打开主窗口", menu)
        self.open_action.triggered.connect(self._window.open_main)

        self.autostart_action = QAction("开机自启", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.toggled.connect(self._on_autostart_toggled)

        self.float_action = QAction("桌面悬浮面板", menu)
        self.float_action.setCheckable(True)
        self.float_action.setChecked(bool(settings.get("float_mode", False)))
        self.float_action.toggled.connect(self._on_float_toggled)

        self.quit_action = QAction("退出", menu)
        self.quit_action.triggered.connect(self._on_quit)

        menu.addAction(self.open_action)
        menu.addSeparator()
        menu.addAction(self.autostart_action)
        menu.addAction(self.float_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        self.tray.setContextMenu(menu)

        # 左键双击图标 → 打开主窗口（design.md 交互规范）
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._window.open_main()

    def _on_autostart_toggled(self, checked: bool):
        ok = autostart.set_enabled(checked)
        update_settings(autostart=checked)  # 以文件为真相原子更新（v1.14 修复覆盖）
        if not ok:
            self.tray.showMessage(
                APP_NAME, "开机自启设置失败（注册表写入被拒绝）",
                QSystemTrayIcon.MessageIcon.Warning, 3000,
            )

    def set_float_manager(self, float_manager):
        self._float_manager = float_manager

    def _on_float_toggled(self, checked: bool):
        if getattr(self, "_float_manager", None) is not None:
            self._float_manager.set_enabled(checked)

    def _on_quit(self):
        self._window.set_quit_requested(True)
        self._app.quit()

    def notify_once(self, title: str, message: str):
        """气泡提示（一次性，首次关闭窗口时调用）。"""
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)
