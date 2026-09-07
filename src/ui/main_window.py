"""主窗口：顶栏（标题/搜索/存储天数/清空）+ 分组卡片列表 + 状态栏"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import image_store
from config import APP_NAME, load_settings, update_settings
from ui.item_card import ItemCard, summarize

DAYS_OPTIONS = [1, 3, 5]        # 存储天数可选值
MAX_ITEMS = 500                 # 界面最多展示条数
SEARCH_DEBOUNCE_MS = 300
RELOAD_DEBOUNCE_MS = 200


class MainWindow(QMainWindow):
    def __init__(self, db, clipboard, parent=None):
        super().__init__(parent)
        self._db = db
        self._clipboard = clipboard  # QApplication.clipboard() 注入
        self._settings = load_settings()
        self._quit_requested = False   # 关闭窗口=退出（托盘"退出"触发）还是=隐藏
        self._tray_notify_done = False # 首次隐藏气泡只提示一次
        self._expanded_ids = set()     # 展开全文的卡片 id（reload 后恢复）
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self.reload)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)

        self.setWindowTitle(APP_NAME)
        self.resize(900, 640)
        self.setMinimumSize(700, 480)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 8)
        outer.setSpacing(12)

        outer.addWidget(self._build_top_bar())

        # 滚动列表
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setObjectName("listArea")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._list_container)
        outer.addWidget(scroll, stretch=1)

        self.statusBar().showMessage("就绪 — 复制任意内容即可自动记录", 6000)
        self.reload()

    # ---------- 顶栏 ----------

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(12)

        # 标题：程序化图标 + 文字（不用 emoji，跨系统渲染稳定）；主题切换时刷新图标
        from ui.style import make_title_pixmap
        self._title_icon = QLabel()
        self._title_icon.setPixmap(make_title_pixmap(22))
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        title_box.addWidget(self._title_icon)
        title_box.addWidget(title)
        lay.addLayout(title_box)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("搜索文字记录…")
        self.search_edit.setClearButtonEnabled(True)
        # 放大镜为控件内固定图标（光标在其后，不再占用占位文本位置）
        from ui.style import make_search_icon
        self.search_edit.addAction(make_search_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.textChanged.connect(self._on_search_changed)
        lay.addWidget(self.search_edit, stretch=1)

        # 类型检索：全部 / 文本 / 图片（可与关键词组合）
        self.type_combo = QComboBox()
        self.type_combo.setToolTip("按类型筛选：全部 / 文本 / 图片（图片不支持关键词）")
        self.type_combo.addItem("类型: 全部", None)
        self.type_combo.addItem("文本", "text")
        self.type_combo.addItem("图片", "image")
        self.type_combo.currentIndexChanged.connect(lambda _i: self.reload())
        lay.addWidget(self.type_combo)

        lay.addWidget(QLabel("存储:"))
        self.days_combo = QComboBox()
        for d in DAYS_OPTIONS:
            self.days_combo.addItem(f"{d} 天", d)
        current = self._settings.get("storage_days", 3)
        idx = DAYS_OPTIONS.index(current) if current in DAYS_OPTIONS else 1
        self.days_combo.setCurrentIndex(idx)
        self.days_combo.currentIndexChanged.connect(self._on_days_changed)
        lay.addWidget(self.days_combo)

        # 图标按钮：统一线性图标（与放大镜/悬浮面板同一笔触，颜色随主题）
        from theme import get_tokens
        from ui.style import make_gear_icon, make_trash_icon, make_window_icon
        tokens = get_tokens()
        self._tokens = tokens

        self.clear_btn = QPushButton(" 清空")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setIcon(make_trash_icon(16, tokens["danger_text"]))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setToolTip("清空所有未置顶记录")
        self.clear_btn.clicked.connect(self._on_clear)
        lay.addWidget(self.clear_btn)

        self.settings_btn = QPushButton(" 设置")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setIcon(make_gear_icon(16, tokens["primary"]))
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.setToolTip("设置：界面主题、悬浮面板、开机自启等")
        self.settings_btn.clicked.connect(self._on_open_settings)
        lay.addWidget(self.settings_btn)

        # 悬浮面板快捷开关（一级界面直接开启/收起）
        self.float_btn = QPushButton(" 悬浮")
        self.float_btn.setObjectName("floatBtn")
        self.float_btn.setIcon(make_window_icon(16, tokens["primary"]))
        self.float_btn.setIconSize(QSize(16, 16))
        self.float_btn.setToolTip("显示 / 收起桌面悬浮面板")
        self.float_btn.setProperty("activated", "false")
        self.float_btn.clicked.connect(self._on_float_btn)
        lay.addWidget(self.float_btn)
        return bar

    # ---------- 列表加载 ----------

    def reload(self):
        keyword = self.search_edit.text().strip()
        type_filter = self.type_combo.currentData()
        items = self._db.search_items(keyword, MAX_ITEMS, type_filter)
        filtering = bool(keyword or type_filter)

        # 清空列表容器（安全销毁旧卡片）
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._list_layout.addStretch(1)

        if not items:
            self._show_empty("没有找到相关记录" if filtering else "暂无记录 — 复制任意内容后会自动出现在这里")
            return

        pinned = [r for r in items if r[5]]
        normal = [r for r in items if not r[5]]

        if pinned:
            self._add_group_title("▍ 置顶 · 永不过期")
            for row in pinned:
                self._add_card(row)

        self._add_group_title("搜索结果" if filtering else "最近记录")
        for row in normal:
            self._add_card(row)

        # 底部留白 + 状态提示
        self._list_layout.addStretch(1)

    def _show_empty(self, text: str):
        label = QLabel(text)
        label.setObjectName("emptyLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._list_layout.addWidget(label)

    def _add_group_title(self, text: str):
        label = QLabel(text)
        label.setObjectName("groupTitle")
        self._list_layout.addWidget(label)

    def _add_card(self, row):
        card = ItemCard(
            row,
            self._db,
            self._clipboard,
            on_changed=self.reload,
            on_copied=self._on_copied,
            on_about_to_copy=self._before_copy,
            expanded=row[0] in self._expanded_ids,
            on_expand=self._on_card_expand,
        )
        self._list_layout.addWidget(card)

    def _on_card_expand(self, item_id: int, expanded: bool):
        """记录展开状态：刷新列表后仍保持展开，防止长文本"重新折叠"。"""
        if expanded:
            self._expanded_ids.add(item_id)
        else:
            self._expanded_ids.discard(item_id)

    def set_watcher(self, watcher):
        """注入剪贴板监听器（用于复制历史内容时抑制自身监听）。"""
        self._watcher = watcher

    def set_tray_manager(self, tray_manager):
        """注入托盘管理器（用于"关闭=隐藏"时气泡提示）。"""
        self._tray_manager = tray_manager

    def set_quit_requested(self, flag: bool):
        """交易退出请求：为 True 时关闭窗口 = 真正退出程序。"""
        self._quit_requested = flag

    def open_main(self):
        """从托盘/单实例唤醒：显示并置顶主窗口。"""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        """关闭窗口 = 隐藏到托盘继续后台记录；托盘"退出"才真正退出。"""
        if self._quit_requested:
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self._tray_notify_done and getattr(self, "_tray_manager", None) is not None:
            self._tray_notify_done = True
            self._tray_manager.notify_once(
                "剪贴板历史",
                "已最小化到系统托盘，剪贴板仍在后台记录；"
                "双击托盘图标可重新打开，右键托盘图标可退出。",
            )

    def _before_copy(self):
        if getattr(self, "_watcher", None) is not None:
            self._watcher.suppress()

    # ---------- 事件 ----------

    def _on_search_changed(self, _text):
        # 输入防抖：停止输入 300ms 后执行过滤
        self._search_timer.start(SEARCH_DEBOUNCE_MS)

    def _on_days_changed(self, index):
        days = DAYS_OPTIONS[index]
        update_settings(storage_days=days)  # 以文件为真相原子更新（v1.14 修复覆盖）
        self.statusBar().showMessage(f"存储期限已设置为 {days} 天", 3000)

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, on_applied=self._apply_settings)
        dlg.exec()

    def set_hotkey_manager(self, hotkey_manager):
        """注入全局快捷键管理器（设置保存后热生效）。"""
        self._hotkey_manager = hotkey_manager

    def set_theme_manager(self, theme_manager):
        """注入主题管理器：主题切换时刷新图标并重建列表。"""
        self._theme_manager = theme_manager
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _theme: str):
        """主题热切换：标题/搜索/按钮图标换色 + 重建卡片（阴影色适配）。"""
        tokens = self._theme_manager.current_tokens()
        from ui.style import make_gear_icon, make_search_icon, make_title_pixmap, make_trash_icon, make_window_icon
        self._title_icon.setPixmap(make_title_pixmap(22, primary=tokens["primary"]))
        actions = self.search_edit.actions()
        if actions:
            actions[0].setIcon(make_search_icon(color=tokens["icon"]))
        # 顶栏按钮图标换色（悬浮按钮颜色在 _sync_float_btn 里管理）
        self.clear_btn.setIcon(make_trash_icon(16, tokens["danger_text"]))
        self.settings_btn.setIcon(make_gear_icon(16, tokens["primary"]))
        self.float_btn.setIcon(make_window_icon(16, tokens["primary"]))
        self.reload()
        self._sync_float_btn()
    def set_float_manager(self, float_manager):
        """注入悬浮面板管理器：同步按钮状态 + 模式变化时刷新按钮。"""
        self._float_manager = float_manager
        if float_manager is not None:
            float_manager.mode_changed.connect(lambda _v: self._sync_float_btn())
        self._sync_float_btn()

    def _sync_float_btn(self):
        """顶栏悬浮按钮激活态 = 悬浮模式开启（面板可见/收起不影响模式）。"""
        on = bool(getattr(self, "_float_manager", None) is not None
                  and self._float_manager.is_enabled())
        self.float_btn.setProperty("activated", "true" if on else "false")
        # 图标颜色：描边风格下激活/未激活均为主色（与文字一致）
        from theme import get_tokens
        from ui.style import make_window_icon
        tokens = get_tokens()
        self.float_btn.setIcon(make_window_icon(16, tokens["primary"]))
        self.float_btn.style().unpolish(self.float_btn)
        self.float_btn.style().polish(self.float_btn)

    def _on_float_btn(self):
        """顶栏悬浮按钮：模式关 → 开启显示；模式开 + 面板可见 → 收起；模式开 + 已收起 → 再显示。"""
        fp = getattr(self, "_float_manager", None)
        if fp is None:
            return
        if not fp.is_enabled():
            fp.set_enabled(True)
        elif fp.isVisible():
            fp.hide_panel()
        else:
            fp.refresh()
            fp.show()
            fp.raise_()
        self._sync_float_btn()

    def _apply_settings(self, success: bool = True):
        """设置对话框保存后：同步顶栏下拉、应用主题与悬浮模式、提示。"""
        self._settings = load_settings()
        days = self._settings.get("storage_days", 3)
        idx = DAYS_OPTIONS.index(days) if days in DAYS_OPTIONS else 1
        self.days_combo.blockSignals(True)
        self.days_combo.setCurrentIndex(idx)
        self.days_combo.blockSignals(False)
        # 主题由设置对话框保存到 settings，这里让 ThemeManager 读取并热切换
        if getattr(self, "_theme_manager", None) is not None:
            self._theme_manager.set_mode(self._settings.get("theme", "system"))
        # 悬浮模式开关
        if getattr(self, "_float_manager", None) is not None:
            self._float_manager.set_enabled(bool(self._settings.get("float_mode", False)))
        # 唤醒快捷键热生效
        hk_result = None
        if getattr(self, "_hotkey_manager", None) is not None:
            hk_result = self._hotkey_manager.apply_from_settings()
        if not success:
            self.statusBar().showMessage("设置已保存，但开机自启写入失败（可能被安全软件拦截）", 5000)
        elif hk_result is False:
            self.statusBar().showMessage("唤醒快捷键被其他程序占用，已保存但未生效（可选其他组合）", 5000)
        else:
            self.statusBar().showMessage("设置已保存", 3000)

    def _on_clear(self):
        ret = QMessageBox.question(
            self, "清空", "将清空所有未置顶记录（置顶内容保留），确定吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        image_store.remove_files(self._db.clear_unpinned())
        self.statusBar().showMessage("已清空未置顶记录", 3000)
        self.reload()

    def _on_copied(self, kind: str):
        tip = "文本已复制，去目标窗口按 Ctrl+V 粘贴吧" if kind == "text" else "图片已复制，去目标窗口按 Ctrl+V 粘贴吧"
        self.statusBar().showMessage(tip, 4000)

    def on_record_hook(self, kind: str, result: str, summary: str):
        """剪贴板监听器回调：提示 + 防抖刷新列表"""
        tag = "文本" if kind == "text" else "图片"
        action = "已记录" if result == "inserted" else "已更新"
        msg = f"{action} {tag}"
        if kind == "text":
            msg += f"：{summarize(summary, 30)}"
        self.statusBar().showMessage(msg, 4000)
        self._reload_timer.start(RELOAD_DEBOUNCE_MS)
