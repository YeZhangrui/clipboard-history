"""UI 主题样式 —— 设计系统（参考 Kazumi：纯黑底 + 深靛蓝主色 + 大圆角 + 粗体标题）

色板 token（WCAG AA 对比度达标）：
  浅色：Primary #35618E 深靛蓝（白字 5.5:1）  深色：Primary #5CA3E8→ 保持亮蓝风格? 
  背景：浅色纯 #F3F7FB    深色纯黑 #0F0F0F（Kazumi 式平面）
  表面：浅色 #FFFFFF      深色 #1A1A1C
  文字：浅色 #16202C / 深色 #F2F2F2
"""
from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

LIGHT_TOKENS = {
    "primary": "#35618E", "primary_hover": "#2E5680", "primary_active": "#274B70",
    "primary_soft": "#E9F0F7", "primary_soft_hover": "#DBE6F1",
    "bg_grad_top": "#F3F7FB", "bg_grad_bottom": "#F3F7FB",
    "topbar": "rgba(255, 255, 255, 0.95)",
    "surface": "#FFFFFF", "surface_soft": "#EEF3F9", "surface_soft_hover": "#E2EAF3",
    "border": "#DCE7F1", "border_hover": "#9DBBD8", "border_strong": "#C4D6E8",
    "text": "#16202C", "text_secondary": "#52606E", "text_meta": "#64748A",
    "placeholder": "#8A99A8", "muted": "#8A99A8",
    "accent": "#E9A13B", "accent_soft": "#FDF3E3", "accent_soft_hover": "#F8E7C8",
    "danger": "#E35D5D", "danger_text": "#D04848", "danger_soft": "#FDF0F0", "danger_soft_hover": "#FADFDF",
    "icon": "#8A99A8", "icon_soft": "#C3CFDC",
    "scroll": "#C9DAEC", "scroll_hover": "#9FBFE0",
    "status_text": "#35618E",
    "shadow_alpha": 56,
}

DARK_TOKENS = {
    "primary": "#3E6FA5", "primary_hover": "#4E7FB6", "primary_active": "#34608F",
    "primary_soft": "#1C2A3A", "primary_soft_hover": "#243548",
    "bg_grad_top": "#0F0F0F", "bg_grad_bottom": "#0F0F0F",
    "topbar": "rgba(18, 18, 19, 0.97)",
    "surface": "#1A1A1C", "surface_soft": "#242427", "surface_soft_hover": "#2D2D31",
    "border": "#2A2A2E", "border_hover": "#3E4C5C", "border_strong": "#35353A",
    "text": "#F2F2F2", "text_secondary": "#B4BAC2", "text_meta": "#8E959E",
    "placeholder": "#6E747D", "muted": "#6E747D",
    "accent": "#F0B04A", "accent_soft": "#3A3220", "accent_soft_hover": "#4A3F26",
    "danger": "#F07A7A", "danger_text": "#F29595", "danger_soft": "#3A2626", "danger_soft_hover": "#4A2E2E",
    "icon": "#6E747D", "icon_soft": "#48484D",
    "scroll": "#2E2E33", "scroll_hover": "#3E3E44",
    "status_text": "#6FA0D4",
    "shadow_alpha": 96,
}


def build_stylesheet(t: dict) -> str:
    """由色板 token 生成完整 QSS（浅色/深色通用一套结构）。"""
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: {t["text"]};
}}
QMainWindow, QWidget#root {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {t["bg_grad_top"]}, stop:1 {t["bg_grad_bottom"]});
    color: {t["text"]};
}}

/* ================= 顶栏 ================= */
QFrame#topBar {{
    background: {t["topbar"]};
    border: 1px solid {t["border"]};
    border-radius: 16px;
}}
QLabel#titleLabel {{
    font-size: 18px;
    font-weight: 700;
    color: {t["text"]};
    background: transparent;
    letter-spacing: 0.2px;
}}
QLineEdit#searchEdit {{
    background: {t["surface_soft"]};
    border: 1px solid {t["border"]};
    border-radius: 12px;
    padding: 7px 10px;
    font-size: 13px;
    color: {t["text"]};
    placeholder-text-color: {t["placeholder"]};
    selection-background-color: {t["primary"]};
    selection-color: {t["surface"]};
}}
QLineEdit#searchEdit:hover {{ border-color: {t["border_hover"]}; }}
QLineEdit#searchEdit:focus {{
    border: 1px solid {t["primary"]};
    background: {t["surface"]};
}}
QComboBox {{
    background: {t["surface_soft"]};
    border: 1px solid {t["border"]};
    border-radius: 12px;
    padding: 6px 12px;
    min-width: 68px;
    color: {t["text"]};
}}
QComboBox:hover {{ border-color: {t["border_hover"]}; }}
QComboBox:pressed {{ background: {t["surface_soft_hover"]}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    color: {t["text"]};
    selection-background-color: {t["primary_soft"]};
    selection-color: {t["text"]};
    padding: 4px;
    outline: none;
}}
/* 三按钮共享基础样式：大小/圆角/字重完全一致（v1.12 统一） */
QPushButton#clearBtn, QPushButton#settingsBtn, QPushButton#floatBtn {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 12px;
    padding: 7px 14px;
    font-weight: 600;
    color: {t["text"]};
}}
QPushButton#clearBtn {{ color: {t["danger_text"]}; }}
QPushButton#clearBtn:hover {{ background: {t["danger_soft"]}; border-color: {t["danger"]}; }}
QPushButton#clearBtn:pressed {{ background: {t["danger_soft_hover"]}; }}
QPushButton#settingsBtn {{ color: {t["primary"]}; }}
QPushButton#settingsBtn:hover {{ background: {t["primary_soft"]}; border-color: {t["primary"]}; }}
QPushButton#settingsBtn:pressed {{ background: {t["primary_soft_hover"]}; }}
QPushButton#floatBtn {{ color: {t["primary"]}; }}
QPushButton#floatBtn:hover {{ background: {t["primary_soft"]}; border-color: {t["primary"]}; }}
QPushButton#floatBtn:pressed {{ background: {t["primary_soft_hover"]}; }}
QPushButton#floatBtn[activated="true"] {{
    background: {t["primary_soft"]};
    border: 1px solid {t["primary"]};
    color: {t["primary"]};
}}
QPushButton#floatBtn[activated="true"]:hover {{ background: {t["primary_soft_hover"]}; }}

/* ================= 列表与分组 ================= */
QLabel#groupTitle {{
    color: {t["text_secondary"]};
    font-size: 13px;
    font-weight: 700;
    background: transparent;
    padding-left: 8px;
    padding-top: 6px;
}}
QScrollArea#listArea, QScrollArea#listArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t["scroll"]}; border-radius: 5px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {t["scroll_hover"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLabel#emptyLabel {{
    color: {t["muted"]};
    font-size: 14px;
    background: transparent;
    padding-top: 48px;
}}

/* ================= 记录卡片 ================= */
QFrame#card {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 16px;
}}
QFrame#card:hover {{ border-color: {t["border_hover"]}; }}
QFrame#card[copied="true"] {{
    border: 1px solid {t["primary"]};
    background: {t["primary_soft"]};
}}
QLabel#cardText {{
    color: {t["text"]};
    font-size: 14px;
    background: transparent;
}}
QLabel#metaLabel {{
    color: {t["text_meta"]};
    font-size: 12px;
    background: transparent;
}}
QScrollArea#cardTextScroll, QScrollArea#cardTextScroll > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QPushButton#cardLinkBtn {{
    border: none;
    background: transparent;
    color: {t["primary"]};
    font-size: 12px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 6px;
}}
QPushButton#cardLinkBtn:hover {{ background: {t["primary_soft"]}; }}
QPushButton#pinBtn, QPushButton#delBtn {{
    border: none;
    background: transparent;
    border-radius: 8px;
    padding: 2px;
}}
QPushButton#pinBtn {{ font-size: 18px; color: {t["icon_soft"]}; }}
QPushButton#pinBtn:hover {{ color: {t["accent"]}; background: {t["accent_soft"]}; }}
QPushButton#pinBtn:pressed {{ background: {t["accent_soft_hover"]}; }}
QPushButton#pinBtn[pinned="true"] {{ color: {t["accent"]}; }}
QPushButton#delBtn {{ font-size: 15px; color: {t["icon_soft"]}; }}
QPushButton#delBtn:hover {{ color: {t["danger"]}; background: {t["danger_soft"]}; }}
QPushButton#delBtn:pressed {{ background: {t["danger_soft_hover"]}; }}

/* ================= 对话框 ================= */
QDialog {{ background: {t["surface"]}; }}
QDialog QLabel {{ color: {t["text"]}; }}
QLabel#themeHint {{
    color: {t["text_secondary"]};
    font-size: 12px;
    background: transparent;
    padding-left: 2px;
}}
QLabel#infoLabel {{
    color: {t["text_secondary"]};
    font-size: 12px;
    background: {t["surface_soft"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 10px;
}}
QCheckBox {{ color: {t["text"]}; spacing: 8px; font-size: 13px; }}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {t["icon_soft"]};
    border-radius: 5px;
    background: {t["surface"]};
}}
QCheckBox::indicator:hover {{ border-color: {t["primary"]}; }}
QCheckBox::indicator:checked {{
    background: {t["primary"]};
    border-color: {t["primary"]};
}}
QDialog QPushButton {{
    background: {t["surface"]};
    border: 1px solid {t["border_strong"]};
    border-radius: 8px;
    padding: 8px 20px;
    color: {t["text"]};
    min-width: 76px;
    font-weight: 500;
}}
QDialog QPushButton:hover {{ background: {t["surface_soft"]}; border-color: {t["border_hover"]}; }}
QDialog QPushButton:pressed {{ background: {t["surface_soft_hover"]}; }}
QDialog QPushButton:default {{
    background: {t["primary"]};
    border: 1px solid {t["primary"]};
    color: {t["surface"]};
}}
QDialog QPushButton:default:hover {{ background: {t["primary_hover"]}; border-color: {t["primary_hover"]}; }}
QDialog QPushButton:default:pressed {{ background: {t["primary_active"]}; }}

/* ================= 菜单 / 提示 / 确认框 ================= */
QMenu {{
    background: {t["surface"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    background: transparent;
    color: {t["text"]};
    padding: 8px 22px;
    border-radius: 6px;
    font-size: 13px;
}}
QMenu::item:selected {{ background: {t["primary_soft"]}; color: {t["primary"]}; }}
QMenu::separator {{ height: 1px; background: {t["border"]}; margin: 5px 8px; }}
QToolTip {{
    background: {t["surface"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    padding: 5px 9px;
    border-radius: 6px;
    font-size: 12px;
}}
QMessageBox {{
    background: {t["surface"]};
    color: {t["text"]};
}}
QMessageBox QLabel {{ color: {t["text"]}; font-size: 13px; }}
QMessageBox QPushButton {{
    background: {t["surface"]};
    border: 1px solid {t["border_strong"]};
    border-radius: 8px;
    padding: 8px 20px;
    color: {t["text"]};
    min-width: 76px;
    font-weight: 500;
}}
QMessageBox QPushButton:hover {{ background: {t["surface_soft"]}; border-color: {t["border_hover"]}; }}
QMessageBox QPushButton:pressed {{ background: {t["surface_soft_hover"]}; }}
QMessageBox QPushButton:default {{
    background: {t["primary_soft"]};
    border: 1px solid {t["primary"]};
    color: {t["primary"]};
    font-weight: 600;
}}
QMessageBox QPushButton:default:hover {{ background: {t["primary_soft_hover"]}; }}

/* ================= 桌面悬浮模式 ================= */
QFrame#floatCard {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 12px;
}}
QLabel#floatTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {t["text"]};
    background: transparent;
}}
QLineEdit#floatSearch {{
    background: {t["surface_soft"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    padding: 5px 9px;
    font-size: 12px;
    color: {t["text"]};
    placeholder-text-color: {t["placeholder"]};
    selection-background-color: {t["primary"]};
    selection-color: {t["surface"]};
}}
QLineEdit#floatSearch:focus {{
    border: 1px solid {t["primary"]};
    background: {t["surface"]};
}}
QFrame#floatItem {{
    background: {t["surface_soft"]};
    border: 1px solid transparent;
    border-radius: 10px;
}}
QFrame#floatItem:hover {{
    border: 1px solid {t["primary"]};
    background: {t["surface_soft_hover"]};
}}
QFrame#floatItem[copied="true"] {{
    border: 1px solid {t["primary"]};
    background: {t["primary_soft"]};
}}
QLabel#floatText {{
    font-size: 13px;
    color: {t["text"]};
    background: transparent;
}}
QLabel#floatTime {{
    font-size: 11px;
    color: {t["text_meta"]};
    background: transparent;
}}
QPushButton#floatDel, QPushButton#floatCollapse, QPushButton#floatHome {{
    border: none;
    background: transparent;
    border-radius: 6px;
    font-size: 13px;
    color: {t["icon_soft"]};
    padding: 0;
}}
QPushButton#floatDel:hover {{ color: {t["danger"]}; background: {t["danger_soft"]}; }}
QPushButton#floatCollapse:hover {{ color: {t["text"]}; background: {t["surface_soft_hover"]}; }}
QPushButton#floatHome:hover {{ color: {t["primary"]}; background: {t["primary_soft"]}; }}
QLabel#floatEmpty {{
    color: {t["muted"]};
    font-size: 13px;
    background: transparent;
    padding: 20px 0;
}}
QLabel#floatStatus {{
    color: {t["status_text"]};
    font-size: 12px;
    background: transparent;
}}
QScrollArea#floatScroll, QScrollArea#floatScroll > QWidget > QWidget {{
    background: transparent;
    border: none;
}}

/* ================= 状态栏 ================= */
QStatusBar {{
    background: transparent;
    color: {t["status_text"]};
    font-size: 12px;
}}
QStatusBar::item {{ border: none; }}
"""


def search_icon_color(t: dict) -> str:
    return t["icon"]


def make_search_icon(size: int = 18, color: str = "#8A99A8") -> QIcon:
    """搜索框左侧的固定放大镜图标（不占用文本位置，光标在其后）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(size * 0.14, size * 0.14, size * 0.5, size * 0.5))
    p.drawLine(QPointF(size * 0.55, size * 0.55), QPointF(size * 0.85, size * 0.85))
    p.end()
    return QIcon(pm)


def make_home_icon(size: int = 16, color: str = "#8A99A8") -> QIcon:
    """线性风格"房子"图标（与放大镜同一笔触：召唤/收回主界面）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 16.0
    p.drawLine(QPointF(2.5 * s, 7.5 * s), QPointF(7.5 * s, 3.0 * s))    # 左屋顶
    p.drawLine(QPointF(7.5 * s, 3.0 * s), QPointF(13.5 * s, 7.5 * s))   # 右屋顶
    p.drawLine(QPointF(4.5 * s, 7.0 * s), QPointF(4.5 * s, 13.5 * s))   # 左墙
    p.drawLine(QPointF(11.5 * s, 7.0 * s), QPointF(11.5 * s, 13.5 * s)) # 右墙
    p.drawLine(QPointF(4.5 * s, 13.5 * s), QPointF(11.5 * s, 13.5 * s)) # 底
    p.end()
    return QIcon(pm)


def make_close_icon(size: int = 16, color: str = "#8A99A8") -> QIcon:
    """线性风格"关闭"图标（与放大镜同一笔触：收起/删除）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 16.0
    p.drawLine(QPointF(4.0 * s, 4.0 * s), QPointF(12.0 * s, 12.0 * s))
    p.drawLine(QPointF(12.0 * s, 4.0 * s), QPointF(4.0 * s, 12.0 * s))
    p.end()
    return QIcon(pm)


def make_trash_icon(size: int = 16, color: str = "#8A99A8") -> QIcon:
    """线性风格"清空"图标：垃圾桶（盖 + 桶 + 桶身刻度）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 16.0
    p.drawLine(QPointF(3.4 * s, 4.4 * s), QPointF(12.6 * s, 4.4 * s))    # 盖
    p.drawLine(QPointF(6.2 * s, 2.8 * s), QPointF(9.8 * s, 2.8 * s))     # 把手
    p.drawLine(QPointF(4.6 * s, 4.6 * s), QPointF(5.4 * s, 13.4 * s))    # 左桶身
    p.drawLine(QPointF(11.4 * s, 4.6 * s), QPointF(10.6 * s, 13.4 * s))  # 右桶身
    p.drawLine(QPointF(5.4 * s, 13.4 * s), QPointF(10.6 * s, 13.4 * s))  # 底
    p.drawLine(QPointF(7.2 * s, 6.4 * s), QPointF(7.2 * s, 11.4 * s))    # 刻度
    p.drawLine(QPointF(8.8 * s, 6.4 * s), QPointF(8.8 * s, 11.4 * s))    # 刻度
    p.end()
    return QIcon(pm)


def make_gear_icon(size: int = 16, color: str = "#8A99A8") -> QIcon:
    """线性风格"设置"图标：齿轮（外圈 8 齿 + 中心圆孔）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 16.0
    # 8 个齿
    import math
    cx, cy = 8.0 * s, 8.0 * s
    for i in range(8):
        ang = math.radians(i * 45)
        x1 = cx + math.cos(ang) * 5.6 * s
        y1 = cy + math.sin(ang) * 5.6 * s
        x2 = cx + math.cos(ang) * 7.0 * s
        y2 = cy + math.sin(ang) * 7.0 * s
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.drawEllipse(QRectF(cx - 4.4 * s, cy - 4.4 * s, 8.8 * s, 8.8 * s))   # 外圈
    p.drawEllipse(QRectF(cx - 1.9 * s, cy - 1.9 * s, 3.8 * s, 3.8 * s))   # 中心孔
    p.end()
    return QIcon(pm)


def make_window_icon(size: int = 16, color: str = "#8A99A8") -> QIcon:
    """线性风格"悬浮面板"图标：窗口方框 + 顶部标题条短线。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 16.0
    p.drawRect(QRectF(2.6 * s, 3.4 * s, 10.8 * s, 9.6 * s))  # 窗口
    p.drawLine(QPointF(2.6 * s, 6.4 * s), QPointF(13.4 * s, 6.4 * s))  # 标题条
    p.drawLine(QPointF(4.6 * s, 5.0 * s), QPointF(9.4 * s, 5.0 * s))   # 标题短线
    p.end()
    return QIcon(pm)


def make_app_icon(primary: str = "#3D7FC1") -> QIcon:
    """程序化生成剪贴板图标（64x64，托盘/任务栏用）。"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(primary))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRect(4, 4, 56, 56), 14, 14)
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(QRect(18, 17, 28, 33), 5, 5)
    p.setBrush(QColor(primary))
    p.drawRoundedRect(QRect(24, 12, 16, 9), 4, 4)
    p.drawRoundedRect(QRect(25, 26, 14, 3), 1, 1)
    p.drawRoundedRect(QRect(25, 33, 14, 3), 1, 1)
    p.end()
    return QIcon(pm)


def make_title_pixmap(size: int = 22, primary: str = "#3D7FC1", secondary: str = "#FFFFFF") -> QPixmap:
    """顶栏标题小图标（微缩版剪贴板图标，主题色自适应）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64.0
    p.setBrush(QColor(primary))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(4 * s, 4 * s, 56 * s, 56 * s), 14 * s, 14 * s)
    p.setBrush(QColor(secondary))
    p.drawRoundedRect(QRectF(18 * s, 15 * s, 28 * s, 36 * s), 5 * s, 5 * s)
    p.setBrush(QColor(primary))
    p.drawRoundedRect(QRectF(24 * s, 10 * s, 16 * s, 9 * s), 4 * s, 4 * s)
    p.drawRoundedRect(QRectF(25 * s, 26 * s, 14 * s, 3 * s), 1 * s, 1 * s)
    p.drawRoundedRect(QRectF(25 * s, 33 * s, 14 * s, 3 * s), 1 * s, 1 * s)
    p.end()
    return pm
