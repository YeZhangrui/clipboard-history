"""记录卡片组件：内容区（文本摘要/图片缩略图）+ 信息区（类型·时间）+ 置顶/删除 + 点击复制
v1.15：文本卡片「展开全文/收起」动态高度；图片卡片「查看大图」预览窗，防止内容看不全。"""
import datetime
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import image_store
from config import get_data_dir

TEXT_SUMMARY_CHARS = 120   # 文本摘要最大字数
THUMB_SIZE = 128           # 缩略图显示尺寸（px）


def format_time(iso: str) -> str:
    """时间显示规则：今天 HH:MM；今年 MM-DD HH:MM；更早 YYYY-MM-DD"""
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    now = datetime.datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    if dt.year == now.year:
        return dt.strftime("%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


def summarize(text: str, width: int = TEXT_SUMMARY_CHARS) -> str:
    t = " ".join(text.split())
    return t if len(t) <= width else t[: width - 1] + "…"


def _rgba(hex_color: str, alpha: int) -> QColor:
    """#RRGGBB + alpha(0-255) → QColor（带透明度）。"""
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


def _center_window(win):
    """窗口居中到屏幕（适配多屏）。"""
    if win.screen() is None:
        return
    area = win.screen().availableGeometry()
    win.move(area.center() - win.rect().center())


class ImagePreviewDialog(QDialog):
    """大图预览：按屏幕 90% 缩放显示，超大可滚动，Esc/关闭按钮退出。"""

    def __init__(self, img, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        max_w = int(area.width() * 0.9)
        max_h = int(area.height() * 0.9)

        pix = QPixmap.fromImage(img)
        if pix.width() > max_w or pix.height() > max_h:
            pix = pix.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

        label = QLabel()
        label.setPixmap(pix)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll = QScrollArea()
        scroll.setObjectName("listArea")  # 继承透明滚动样式
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(scroll)

        self.resize(min(pix.width() + 24, max_w), min(pix.height() + 24, max_h))
        QTimer.singleShot(0, lambda: _center_window(self))


class _ClickableArea(QWidget):
    """卡片内容区：左键点击即复制到剪贴板"""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ItemCard(QFrame):
    """单条记录卡片。row 结构（与 database 查询列一致）：
    (id, type, content, image_path, thumbnail_path, pinned, created_at, updated_at)"""

    def __init__(self, row, db, clipboard, on_changed=None, on_copied=None,
                 on_about_to_copy=None, expanded=False, on_expand=None, parent=None):
        super().__init__(parent)
        self._row = row
        self._db = db
        self._clipboard = clipboard
        self._on_changed = on_changed   # 数据变化（置顶/删除）后通知窗口刷新
        self._on_copied = on_copied     # 复制成功后通知窗口提示
        self._on_about_to_copy = on_about_to_copy  # 复制前通知窗口（用于抑制自身监听）
        self._on_expand = on_expand     # 展开状态变化通知（窗口记忆，reload 后恢复）
        self._expanded = bool(expanded)
        self.setObjectName("card")

        rid, typ, content, img_path, thumb_path, pinned, created, updated = row
        self._item_id = rid
        self._type = typ
        self._content = content
        self._image_path = img_path      # 原图（点击复制用，保证画质与指纹一致）
        self._thumb_path = thumb_path    # 缩略图（仅列表显示用）

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(16)

        # ---- 内容区（点击复制，占满剩余空间）----
        content_area = _ClickableArea()
        content_area.setCursor(Qt.CursorShape.PointingHandCursor)
        content_area.setToolTip("点击即可复制到剪贴板，然后到目标窗口按 Ctrl+V")
        c_lay = QVBoxLayout(content_area)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(2)

        if typ == "text":
            # 文本区：滚动容器（折叠=摘要两行；展开=限高滚动浏览全文，永不截断）
            self._text_scroll = QScrollArea()
            self._text_scroll.setObjectName("cardTextScroll")
            self._text_scroll.setWidgetResizable(True)
            self._text_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._text_label = QLabel(content or "")
            self._text_label.setObjectName("cardText")
            self._text_label.setWordWrap(True)
            self._text_label.setToolTip(content or "")
            self._text_scroll.setWidget(self._text_label)
            self._text_scroll.setFixedHeight(320 if self._expanded else 48)  # 约 2 行
            c_lay.addWidget(self._text_scroll)

            # 展开全文 / 收起（动态高度，防止长文本看不全）
            if len(content or "") > TEXT_SUMMARY_CHARS:
                self._expand_btn = QPushButton("收起 ▴" if self._expanded else "展开全文 ▾")
                self._expand_btn.setObjectName("cardLinkBtn")
                self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self._expand_btn.clicked.connect(self._toggle_expand)
                c_lay.addWidget(self._expand_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            pix = QPixmap(os.path.join(get_data_dir(), thumb_path or img_path or ""))
            if pix.isNull():
                pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
            pix = pix.scaled(
                THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label = QLabel()
            img_label.setPixmap(pix)
            img_label.setCursor(Qt.CursorShape.PointingHandCursor)
            img_label.setToolTip("点击复制此图片；下方「查看大图」可看全图")
            c_lay.addWidget(img_label)
            # 查看大图（防止缩略图看不全）
            self._preview_btn = QPushButton("查看大图")
            self._preview_btn.setObjectName("cardLinkBtn")
            self._preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._preview_btn.clicked.connect(self._show_preview)
            c_lay.addWidget(self._preview_btn, alignment=Qt.AlignmentFlag.AlignLeft)
            c_lay.addStretch(1)  # 缩略图靠上，下方留白由内容区决定

        content_area.clicked.connect(self._copy_to_clipboard)
        lay.addWidget(content_area, stretch=1)

        # ---- 右侧信息区（垂直居中：类型·时间 + 操作按钮）----
        right = QVBoxLayout()
        right.setSpacing(8)

        meta = QLabel(f"{'图片' if typ == 'image' else '文本'} · {format_time(updated)}")
        meta.setObjectName("metaLabel")
        meta.setAlignment(Qt.AlignmentFlag.AlignRight)

        btns = QHBoxLayout()
        btns.setSpacing(4)
        btns.addStretch(1)

        pin_btn = QPushButton("★" if pinned else "☆")
        pin_btn.setObjectName("pinBtn")
        pin_btn.setProperty("pinned", "true" if pinned else "false")
        pin_btn.setToolTip("取消置顶" if pinned else "置顶（永不过期）")
        pin_btn.setFixedSize(32, 30)
        pin_btn.clicked.connect(self._toggle_pin)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("delBtn")
        del_btn.setToolTip("删除此记录")
        del_btn.setFixedSize(32, 30)
        del_btn.clicked.connect(self._confirm_delete)

        btns.addWidget(pin_btn)
        btns.addWidget(del_btn)

        right.addStretch(1)
        right.addWidget(meta)
        right.addLayout(btns)
        right.addStretch(1)
        lay.addLayout(right)

        # 悬浮阴影：默认关闭（列表安静），hover 时开启（Material 悬浮层级）；
        # 颜色随当前主题（浅色主色光晕 / 深色亮蓝光晕）
        from theme import get_tokens
        tokens = get_tokens()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(_rgba(tokens["primary"], tokens["shadow_alpha"]))
        shadow.setEnabled(False)
        self.setGraphicsEffect(shadow)
        self._shadow = shadow

    def enterEvent(self, event):
        self._shadow.setEnabled(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._shadow.setEnabled(False)
        super().leaveEvent(event)

    # ---------- 行为 ----------

    def _toggle_expand(self):
        """展开全文 / 收起（滚动区高度 48px ↔ 320px，内容始终完整无截断）。"""
        self._expanded = not self._expanded
        self._text_scroll.setFixedHeight(320 if self._expanded else 48)
        self._expand_btn.setText("收起 ▴" if self._expanded else "展开全文 ▾")
        # 强制整条布局链重算（嵌套 QWidget 不自动传播 heightForWidth）
        self.updateGeometry()
        if self.layout() is not None:
            self.layout().invalidate()
            self.layout().activate()
        self.adjustSize()
        if self._on_expand:
            self._on_expand(self._item_id, self._expanded)

    def _show_preview(self):
        """大图预览对话框（防止缩略图看不全原图内容）。"""
        img = image_store.load_image(self._image_path or "")
        if img.isNull():
            QMessageBox.warning(self, "预览失败", "图片文件缺失或已损坏")
            return
        dlg = ImagePreviewDialog(img, self)
        dlg.exec()

    def _copy_to_clipboard(self):
        if self._on_about_to_copy:
            self._on_about_to_copy()  # 抑制自身监听，避免点击复用产生新记录
        try:
            if self._type == "text":
                self._clipboard.setText(self._content or "")
            else:
                # 复制原图（保证画质；缩略图仅供列表显示）
                img = image_store.load_image(self._image_path or "")
                if img.isNull():
                    raise OSError("图片文件缺失")
                self._clipboard.setImage(img)
        except Exception as exc:  # 异常不崩溃，提示即可
            QMessageBox.warning(self, "复制失败", f"无法复制该内容：\n{exc}")
            return
        self._flash_copied()
        if self._on_copied:
            self._on_copied(self._type)

    def _toggle_pin(self):
        self._db.set_pinned(self._item_id, 0 if self._row[5] else 1)
        if self._on_changed:
            self._on_changed()

    def _confirm_delete(self):
        ret = QMessageBox.question(
            self, "删除记录", "确定删除这条记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        image_store.remove_files(self._db.delete_item(self._item_id))
        if self._on_changed:
            self._on_changed()

    def _flash_copied(self):
        """复制成功：卡片高亮 1 秒提示"""
        self.setProperty("copied", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        QTimer.singleShot(1200, self._clear_flash)

    def _clear_flash(self):
        self.setProperty("copied", "false")
        self.style().unpolish(self)
        self.style().polish(self)
