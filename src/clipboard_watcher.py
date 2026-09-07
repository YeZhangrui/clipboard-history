"""剪贴板监听器（阶段 3：文本 + 图片，文本优先；支持自我抑制）"""
import time

from PySide6.QtCore import QObject
from PySide6.QtGui import QClipboard

import image_store

SUPPRESS_WINDOW_MS = 500  # 抑制窗口：软件自身写剪贴板后，忽略这段时间内的变化


class ClipboardWatcher(QObject):
    """监听系统剪贴板变化，文本/图片内容自动入库。"""

    def __init__(self, app, db, on_record=None):
        super().__init__()
        self._app = app
        self._db = db
        self._on_record = on_record  # 可选回调 (kind, result, summary)
        self._suppress_until = 0.0   # 抑制截止时间（time.time() 秒）
        self._clipboard: QClipboard = app.clipboard()
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def suppress(self, ms: int = SUPPRESS_WINDOW_MS):
        """抑制接下来 ms 毫秒内的剪贴板变化（用于软件自身复制历史内容时，避免产生新记录）。"""
        self._suppress_until = time.time() + ms / 1000.0

    def _is_suppressed(self) -> bool:
        return time.time() < self._suppress_until

    def _on_data_changed(self):
        # 软件自己把历史内容放回剪贴板 → 无视，避免“点击卡片生成重复卡片”
        if self._is_suppressed():
            return
        # 剪贴板只保留"最近状态"，必须同步落库，防止后续复制覆盖
        text = self._clipboard.text()
        if text and text.strip():
            # 文本优先：Word/Excel 复制文字时会同时带位图，应记录为文本
            result = self._db.add_text(text)
            if self._on_record:
                self._on_record("text", result, text)
            return

        img = self._clipboard.image()
        if img is not None and not img.isNull():
            h, rel, thumb_rel = image_store.save_image(img)
            result = self._db.add_image(h, rel, thumb_rel)
            if self._on_record:
                self._on_record("image", result, "")
