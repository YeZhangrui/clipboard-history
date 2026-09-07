"""桌面悬浮模式：常驻置顶小面板（无悬浮球）。

- 面板：无边框（Frameless + Tool + StayOnTop），圆角卡片 + 阴影，320×430
- 常驻桌面：开启即显示，按住头部拖动换位置，位置记忆
- 头部：图标 + 标题 + ✕ = 关闭悬浮模式（发出 close_requested，供调用方同步勾选）
- 内容：最近 20 条 + 搜索过滤；条目点击复制原内容（抑制自身监听）；hover 显示删除
- 主题：跟随全局 token（浅色/深色自动适配）
"""
import os

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

import image_store
from config import APP_NAME, get_data_dir, load_settings, update_settings
from theme import get_tokens
from ui.item_card import format_time, summarize
from ui.style import make_close_icon, make_home_icon, make_title_pixmap

MAX_ITEMS = 20          # 面板显示条数
PANEL_W, PANEL_H = 320, 430
REFRESH_MS = 1500       # 列表轮询刷新（与主窗口数据自动同步）


class _StylishGrip(QSizeGrip):
    """缩放手柄：经典三点圆点（与主界面系统级缩放手柄一致的点状）。"""

    def paintEvent(self, _event):
        tokens = get_tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(tokens["icon"]))
        p.setPen(Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        r = 1.3
        p.drawEllipse(QPointF(w - 10.5, h - 4.5), r, r)
        p.drawEllipse(QPointF(w - 7.5, h - 7.5), r, r)
        p.drawEllipse(QPointF(w - 4.5, h - 10.5), r, r)
        p.end()


class FloatItem(QFrame):
    """面板内条目：点击复制原内容；hover 显示删除。"""

    def __init__(self, row, db, clipboard, on_copied=None, on_changed=None):
        super().__init__()
        self.setObjectName("floatItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击复制；悬浮后点 ✕ 删除")
        self._row = row
        self._db = db
        self._clipboard = clipboard
        self._on_copied = on_copied
        self._on_changed = on_changed

        rid, typ, content, img_path, thumb_path, pinned, created, updated = row
        self._item_id = rid
        self._type = typ
        self._content = content
        self._image_path = img_path

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        lay.setSpacing(10)

        # 内容：文本摘要 2 行 / 缩略图
        if typ == "text":
            body = summarize(content, 60) if content else ""
            label = QLabel(body)
            label.setObjectName("floatText")
            label.setWordWrap(True)
            label.setMaximumHeight(42)
            label.setToolTip(content or "")
            lay.addWidget(label, stretch=1)
        else:
            pix = QPixmap(os.path.join(get_data_dir(), thumb_path or img_path or "")) if (thumb_path or img_path) else QPixmap()
            if pix.isNull():
                pix = QPixmap(60, 44)
            pix = pix.scaled(120, 60, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            label = QLabel()
            label.setPixmap(pix)
            label.setMaximumHeight(56)
            lay.addWidget(label, stretch=1)

        # 右侧：时间 + 删除（hover 显示）
        right = QVBoxLayout()
        right.setSpacing(4)
        time_label = QLabel(format_time(updated))
        time_label.setObjectName("floatTime")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        del_btn = QPushButton()
        del_btn.setObjectName("floatDel")
        del_btn.setFixedSize(22, 20)
        tools = get_tokens()
        del_btn.setIcon(make_close_icon(14, tools["icon"]))
        del_btn.setIconSize(QSize(14, 14))
        del_btn.setToolTip("删除此记录")
        del_btn.setVisible(False)
        del_btn.clicked.connect(self._delete)
        right.addWidget(time_label)
        right.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(right)

        self._del_btn = del_btn

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._copy()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._del_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._del_btn.setVisible(False)
        super().leaveEvent(event)

    def _copy(self):
        if self._on_copied:
            self._on_copied()  # 抑制自身监听
        try:
            if self._type == "text":
                self._clipboard.setText(self._content or "")
            else:
                img = image_store.load_image(self._image_path or "")
                if img.isNull():
                    raise OSError("图片文件缺失")
                self._clipboard.setImage(img)
        except Exception:
            return
        self.setProperty("copied", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        QTimer.singleShot(900, self._clear_copied)

    def _clear_copied(self):
        self.setProperty("copied", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _delete(self):
        image_store.remove_files(self._db.delete_item(self._item_id))
        if self._on_changed:
            self._on_changed()


class _DragHandle(QWidget):
    """头部拖动手柄：按住移动 → 拖动面板（几何保存由面板 moveEvent 防抖处理）。"""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._owner.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._owner.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None


class FloatPanel(QWidget):
    """桌面悬浮面板（常驻置顶）。set_enabled(True/False) 控制模式开关；
    hide_panel() 仅收起（模式保持）；✕ = 收起；🏠 = 召唤/收回主界面。"""

    mode_changed = Signal(bool)  # 模式开关变化（供主窗口顶栏按钮/托盘同步）

    def __init__(self, app, db, watcher, settings=None, on_toggle_main=None):
        super().__init__(None)
        self._app = app
        self._db = db
        self._watcher = watcher
        self._settings = settings or load_settings()
        self._enabled = False
        self._on_toggle_main = on_toggle_main  # 头部 🏠：主界面隐藏→召唤；显示→收回

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(240, 240)          # 可拖拽调整大小（右下角手柄）
        self._geometry_loaded = False          # 恢复几何后置 True（跳过首次保存）
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._save_geometry)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)   # 无阴影留白，卡片贴边
        card = QFrame()
        card.setObjectName("floatCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(8)

        tokens = get_tokens()

        # 头部（拖动手柄）：图标 + 标题 + ⌂(图标)召唤/收回主界面 + ✕(图标)收起
        header = _DragHandle(self)
        header.setToolTip("按住此处可拖动面板")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(2, 2, 0, 2)
        h_lay.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(make_title_pixmap(18, primary=tokens["primary"]))
        title = QLabel(f"{APP_NAME}")
        title.setObjectName("floatTitle")
        h_lay.addWidget(icon)
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        home = QPushButton()
        home.setObjectName("floatHome")
        home.setFixedSize(24, 24)
        home.setIcon(make_home_icon(16, tokens["icon"]))
        home.setIconSize(QSize(16, 16))
        home.setToolTip("召唤 / 收回主界面")
        home.clicked.connect(self._open_main)
        h_lay.addWidget(home)
        collapse = QPushButton()
        collapse.setObjectName("floatCollapse")
        collapse.setFixedSize(24, 24)
        collapse.setIcon(make_close_icon(16, tokens["icon"]))
        collapse.setIconSize(QSize(16, 16))
        collapse.setToolTip("收起面板（主界面顶栏或托盘可再次打开）")
        collapse.clicked.connect(self.hide_panel)
        h_lay.addWidget(collapse)
        lay.addWidget(header)

        # 搜索 + 类型筛选（全部/文本/图片）
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("floatSearch")
        self.search_edit.setPlaceholderText("搜索文字记录…")
        self.search_edit.textChanged.connect(self.refresh)
        search_row.addWidget(self.search_edit, stretch=1)
        self.type_combo = QComboBox()
        self.type_combo.addItem("全部", None)
        self.type_combo.addItem("文本", "text")
        self.type_combo.addItem("图片", "image")
        self.type_combo.currentIndexChanged.connect(lambda _i: self.refresh())
        search_row.addWidget(self.type_combo)
        lay.addLayout(search_row)

        # 列表 + 右下角缩放手柄
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setObjectName("floatScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._list_container)
        lay.addWidget(scroll, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch(1)
        grip = _StylishGrip(self)
        grip.setFixedSize(18, 18)
        grip.setToolTip("拖动此处调整面板大小")
        bottom.addWidget(grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        lay.addLayout(bottom)

        # 底部状态（复制提示）
        self.status_label = QLabel("")
        self.status_label.setObjectName("floatStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)
        lay.addWidget(self.status_label)

        outer.addWidget(card)
        # 无阴影/无渐变：面板干净贴边（透明背景仅用于圆角）

        self._restore_geometry()

        # 定时刷新：与主窗口数据自动同步（每 1.5s）
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(REFRESH_MS)

    # ---------- 开关 ----------

    def set_enabled(self, enabled: bool):
        """模式开关：开 = 显示面板；关 = 隐藏并退出悬浮模式。"""
        self._enabled = bool(enabled)
        if self._enabled:
            self.refresh()
            self.show()
            self.raise_()
        else:
            self.hide()
        update_settings(float_mode=self._enabled)  # 以文件为真相原子更新（v1.14 修复覆盖）
        self.mode_changed.emit(self._enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def hide_panel(self):
        """✕：暂时收起面板（悬浮模式保持开启，主界面顶栏/托盘可再次打开）。"""
        self.hide()

    def _open_main(self):
        """🏠：召唤 / 收回主界面（toggle，由回调实现）。"""
        if self._on_toggle_main is not None:
            self._on_toggle_main()

    # ---------- 位置与大小 ----------

    def moveEvent(self, event):
        super().moveEvent(event)
        self._geometry_timer.start(400)   # 防抖保存

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._geometry_timer.start(400)

    def _save_geometry(self):
        """保存面板几何（位置 + 大小），用户拖动/缩放后自动记忆。"""
        if not self._geometry_loaded:
            return
        pos, size = self.pos(), self.size()
        update_settings(float_pos={"x": pos.x(), "y": pos.y(), "w": size.width(), "h": size.height()})

    def _restore_geometry(self):
        pos = self._settings.get("float_pos") or {}
        try:
            x, y = int(pos.get("x")), int(pos.get("y"))
            w, h = int(pos.get("w", PANEL_W)), int(pos.get("h", PANEL_H))
        except (TypeError, ValueError):
            # 默认：屏幕右上角（距边 24px），默认大小 320×430
            screen = self.screen().availableGeometry()
            x = max(screen.left() + 24, screen.right() - PANEL_W - 24)
            y = screen.top() + 24
            w, h = PANEL_W, PANEL_H
        self.resize(max(w, 240), max(h, 240))
        self.move(x, y)
        self._geometry_loaded = True

    # ---------- 列表刷新 ----------

    def refresh(self):
        keyword = self.search_edit.text().strip()
        type_filter = self.type_combo.currentData()
        items = self._db.search_items(keyword, MAX_ITEMS, type_filter)
        filtering = bool(keyword or type_filter)
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not items:
            label = QLabel("暂无记录" if not filtering else "没有找到相关记录")
            label.setObjectName("floatEmpty")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.addWidget(label)
        else:
            for row in items:
                self._list_layout.addWidget(FloatItem(
                    row, self._db, self._app.clipboard(),
                    on_copied=self._before_copy,
                    on_changed=self.refresh,
                ))
        self._list_layout.addStretch(1)

    def _before_copy(self):
        if self._watcher is not None:
            self._watcher.suppress()
