"""设置对话框：开机自启 / 存储天数 / 数据位置说明"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

import autostart
from config import APP_NAME, get_data_dir, load_settings, save_settings
from hotkey import ROLES
from theme import effective_theme, get_mode_from_settings

DAYS_OPTIONS = [1, 3, 5]
THEME_OPTIONS = [("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")]


class SettingsDialog(QDialog):
    def __init__(self, parent=None, on_applied=None):
        super().__init__(parent)
        self._on_applied = on_applied
        settings = load_settings()
        self._orig_days = settings.get("storage_days", 3)

        self.setWindowTitle(f"{APP_NAME} — 设置")
        self.setModal(True)
        self.setMinimumWidth(380)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # 开机自启
        self.autostart_check = QCheckBox("开机自动启动（后台常驻，不打扰）")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow("开机自启", self.autostart_check)

        # 存储天数
        self.days_combo = QComboBox()
        for d in DAYS_OPTIONS:
            self.days_combo.addItem(f"{d} 天", d)
        idx = DAYS_OPTIONS.index(self._orig_days) if self._orig_days in DAYS_OPTIONS else 1
        self.days_combo.setCurrentIndex(idx)
        form.addRow("存储期限", self.days_combo)

        # 界面主题
        self.theme_combo = QComboBox()
        for key, label in THEME_OPTIONS:
            self.theme_combo.addItem(label, key)
        current_theme = get_mode_from_settings()
        self.theme_combo.setCurrentIndex(
            next((i for i, (k, _l) in enumerate(THEME_OPTIONS) if k == current_theme), 2)
        )
        form.addRow("界面主题", self.theme_combo)

        # 当前生效主题提示（紧跟"界面主题"行下方：模式为「跟随系统」时显示实际生效颜色）
        dark = effective_theme() == "dark"
        hint = QLabel(f"当前生效：{'深色' if dark else '浅色'}（模式设为「跟随系统」时，会随 Windows 设置自动切换）")
        hint.setObjectName("themeHint")
        hint.setWordWrap(True)
        form.addRow("", hint)

        # 桌面悬浮面板
        self.float_check = QCheckBox("桌面悬浮面板（主界面顶栏“▣ 悬浮”可随时开启/收起）")
        self.float_check.setChecked(bool(settings.get("float_mode", False)))
        form.addRow("悬浮面板", self.float_check)

        # 唤醒快捷键（主界面）
        self.hotkey_combo = QComboBox()
        for name in ROLES["main"]["presets"]:
            self.hotkey_combo.addItem(name, name)
        current_hk = settings.get("hotkey", ROLES["main"]["default"])
        self.hotkey_combo.setCurrentIndex(
            next((i for i in range(self.hotkey_combo.count()) if self.hotkey_combo.itemData(i) == current_hk), 0)
        )
        form.addRow("主界面快捷键", self.hotkey_combo)

        # 悬浮面板快捷键
        self.float_hotkey_combo = QComboBox()
        for name in ROLES["float"]["presets"]:
            self.float_hotkey_combo.addItem(name, name)
        current_fk = settings.get("hotkey_float", ROLES["float"]["default"])
        self.float_hotkey_combo.setCurrentIndex(
            next((i for i in range(self.float_hotkey_combo.count()) if self.float_hotkey_combo.itemData(i) == current_fk), 0)
        )
        form.addRow("悬浮面板快捷键", self.float_hotkey_combo)

        lay.addLayout(form)

        # 说明与数据位置
        info = QLabel(
            "说明：置顶的记录永不过期；到期内容自动清理。\n"
            f"数据位置：{get_data_dir()}\n"
            "数据仅保存在本机，软件不联网、不上传。"
        )
        info.setObjectName("infoLabel")
        info.setWordWrap(True)
        lay.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)  # 主色实心样式
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def accept(self):
        """点击确定：应用设置并保存。"""
        settings = load_settings()
        settings["storage_days"] = self.days_combo.currentData()
        settings["theme"] = self.theme_combo.currentData()
        settings["float_mode"] = self.float_check.isChecked()
        settings["hotkey"] = self.hotkey_combo.currentData()
        settings["hotkey_float"] = self.float_hotkey_combo.currentData()

        checked = self.autostart_check.isChecked()
        settings["autostart"] = checked
        ok = autostart.set_enabled(checked)
        save_settings(settings)

        if self._on_applied:
            self._on_applied(success=ok)
        super().accept()
