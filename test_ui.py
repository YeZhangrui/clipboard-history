"""UI 冒烟测试（阶段 3）：offscreen 模式验证窗口构建、卡片数量、分组、搜索过滤。
运行：python test_ui.py
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

import image_store
from database import Database
from ui.item_card import ItemCard
from ui.main_window import MainWindow


def cards_of(win) -> list:
    found = []
    for i in range(win._list_layout.count()):
        w = win._list_layout.itemAt(i).widget()
        if isinstance(w, ItemCard):
            found.append(w)
    return found


def group_titles(win) -> list:
    found = []
    for i in range(win._list_layout.count()):
        w = win._list_layout.itemAt(i).widget()
        if w is not None and w.objectName() == "groupTitle":
            found.append(w.text())
    return found


def main() -> int:
    print("== UI 冒烟测试开始 ==")
    app = QApplication(sys.argv)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(tmp.name)

    # 准备数据：2 文本 + 1 图片
    db.add_text("冒烟测试文字一：你好，剪贴板历史界面。")
    db.add_text("冒烟测试文字二：今晚吃火锅")
    img = QImage(120, 80, QImage.Format.Format_RGB32)
    img.fill(0x4A90D9FF)
    h, rel, thumb = image_store.save_image(img)
    db.add_image(h, rel, thumb)

    win = MainWindow(db, app.clipboard())
    win.reload()
    n1 = len(cards_of(win))
    assert n1 == 3, f"应显示 3 张卡片，实际 {n1}"
    assert "最近记录" in group_titles(win), "应有“最近记录”分组标题"
    assert group_titles(win).count("最近记录") == 1
    print(f"  [OK] 1. 列表构建：{n1} 张卡片 + 分组标题")

    # --- 1.5 类型检索：切到"图片"只显示图片，全部恢复 ---
    assert win.type_combo.count() == 3, "类型筛选应有 全部/文本/图片"
    win.type_combo.setCurrentIndex(2)  # 图片
    app.processEvents()
    img_cards = [c for c in cards_of(win) if c._type == "image"]
    assert len(img_cards) == 1 and len(cards_of(win)) == 1, "图片筛选应只显示图片卡"
    win.type_combo.setCurrentIndex(0)  # 全部
    app.processEvents()
    assert len(cards_of(win)) == 3, "恢复全部筛选"
    print("  [OK] 1.5 类型检索：图片/全部 过滤")

    # 置顶后应进入置顶分组
    target = [c for c in cards_of(win) if c._type == "image"][0]
    target._toggle_pin()
    win.reload()
    cards = cards_of(win)
    assert cards[0]._item_id == target._item_id, "置顶卡片应排最前"
    assert any("置顶" in t for t in group_titles(win)), "应有置顶分组标题"
    pinned_cards = [c for c in cards if c._row[5]]
    assert len(pinned_cards) == 1, f"应有 1 张置顶卡片，实际 {len(pinned_cards)}"
    print("  [OK] 2. 置顶分组：置顶卡片排最前，分组标题正确")

    # 搜索过滤
    win.search_edit.setText("火锅")
    win.reload()
    s_cards = cards_of(win)
    assert len(s_cards) == 1 and "火锅" in s_cards[0]._content, "搜索应只命中 1 张文本卡片"
    assert "搜索结果" in group_titles(win), "搜索时分组标题应为“搜索结果”"
    print("  [OK] 3. 搜索过滤：命中 1 张卡片")

    # 清空搜索恢复完整列表
    win.search_edit.setText("")
    win.reload()
    assert len(cards_of(win)) == 3, "清空搜索应恢复 3 张卡片"
    print("  [OK] 4. 恢复完整列表")

    # 空数据状态
    image_store.remove_files(db.clear_all())
    win.reload()
    empty = [w for i in range(win._list_layout.count())
             if (w := win._list_layout.itemAt(i).widget()) is not None
             and w.objectName() == "emptyLabel"]
    assert len(empty) == 1, "无数据时应显示空状态提示"
    print("  [OK] 5. 空状态提示")

    # 无数据时搜索无结果
    win.search_edit.setText("不存在")
    win.reload()
    assert len(cards_of(win)) == 0, "无结果时不应有卡片"
    print("  [OK] 6. 搜索无结果状态")

    # --- 7. 点击卡片复制不产生新记录（抑制自身监听）---
    win.search_edit.setText("")  # 清掉残留搜索词，恢复完整列表
    win.reload()
    db.add_text("抑制测试用文字")
    db.add_text("抑制测试用文字二")
    img = QImage(100, 70, QImage.Format.Format_RGB32)
    img.fill(0x4A90D9FF)
    h, rel, thumb = image_store.save_image(img)
    db.add_image(h, rel, thumb)
    win.reload()

    from clipboard_watcher import ClipboardWatcher
    watcher = ClipboardWatcher(app, db)
    win.set_watcher(watcher)
    cnt = db.count()
    img_card = [c for c in cards_of(win) if c._type == "image"][0]
    img_card._copy_to_clipboard()          # 内部：抑制 + setImage（原图）
    watcher._on_data_changed()             # 模拟剪贴板变化（真实由 Qt 触发）
    assert db.count() == cnt, f"点击复制后不应新增记录（{cnt} -> {db.count()}）"
    print("  [OK] 7. 点击卡片复制不产生新记录（抑制自身监听，复制的是原图）")

    # --- 8. 关闭窗口 = 隐藏到托盘；唤起恢复；退出请求后真正关闭 ---
    win.show()
    app.processEvents()
    win.close()
    app.processEvents()
    assert not win.isVisible(), "关闭后窗口应隐藏（继续后台监听）"
    win.open_main()
    app.processEvents()
    assert win.isVisible(), "唤起后窗口应重新显示"
    win.set_quit_requested(True)
    win.close()
    print("  [OK] 8. 关闭=隐藏到托盘；双击唤起恢复；退出请求后真正关闭")

    # --- 9. 搜索框固定图标 + 设置对话框 ---
    assert len(win.search_edit.actions()) >= 1, "搜索框应有前置放大镜图标（不占光标位置）"
    from PySide6.QtWidgets import QDialog, QCheckBox
    from ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(parent=win)
    assert isinstance(dlg, QDialog), "设置对话框应可创建"
    assert dlg.autostart_check is not None and isinstance(dlg.autostart_check, QCheckBox)
    assert dlg.days_combo.count() == 3, "存储期限应有 1/3/5 三个选项"
    assert dlg.theme_combo.count() == 3, "界面主题应有 浅色/深色/跟随系统 三个选项"
    assert dlg.theme_combo.itemData(1) == "dark", "第二项应为深色"
    assert dlg.float_check is not None, "设置应有桌面悬浮模式开关"
    assert dlg.hotkey_combo.count() == 5, "主界面快捷键应有 5 个选项"
    assert dlg.hotkey_combo.findData("Ctrl+Shift+V") == 0, "默认应为 Ctrl+Shift+V"
    assert dlg.float_hotkey_combo.count() == 5, "悬浮面板快捷键应有 5 个选项"
    assert dlg.float_hotkey_combo.findData("Ctrl+Shift+F") == 0, "默认应为 Ctrl+Shift+F"
    dlg.close()
    assert win.settings_btn is not None, "顶栏应有设置按钮" if hasattr(win, "settings_btn") else True
    print("  [OK] 9. 搜索框固定放大镜图标 + 设置对话框（开机自启/存储期限/说明）")

    # --- 10. 桌面悬浮面板：开关/列表/复制/搜索/收起与顶栏快捷开关/回主界面 ---
    from ui.float_panel import FloatPanel
    from ui.float_panel import FloatItem
    fp = FloatPanel(app, db, watcher)
    win.set_float_manager(fp)
    assert not fp.isVisible(), "默认不显示悬浮面板"
    assert win.float_btn.property("activated") != "true", "未开启时顶栏按钮应为未激活"
    # 大小可调（右下角手柄）：resize 生效 + 最小尺寸约束
    fp.resize(420, 540)
    app.processEvents()
    assert (fp.width(), fp.height()) == (420, 540), f"应可调整大小，实际 {fp.width()}x{fp.height()}"
    fp.resize(100, 80)
    app.processEvents()
    assert fp.width() >= 240 and fp.height() >= 240, "应限制最小尺寸 240x240"
    fp.resize(320, 430)
    fp.set_enabled(True)
    assert fp.isVisible(), "开启后悬浮面板应显示"
    assert win.float_btn.property("activated") == "true", "开启后顶栏按钮应激活"
    fp.refresh()
    items = [w for i in range(fp._list_layout.count())
             if isinstance((w := fp._list_layout.itemAt(i).widget()), FloatItem)]
    cnt = db.count()
    assert len(items) == cnt, f"面板应显示 {cnt} 条，实际 {len(items)}"
    # 点击面板条目复制：不产生新记录
    before = db.count()
    items[0]._copy()
    watcher._on_data_changed()
    assert db.count() == before, "悬浮面板点击复制不应新增记录"
    # 搜索过滤
    fp.search_edit.setText("文字二")
    fp.refresh()
    items2 = [w for i in range(fp._list_layout.count())
              if isinstance((w := fp._list_layout.itemAt(i).widget()), FloatItem)]
    assert len(items2) == 1, f"悬浮面板搜索应命中 1 条，实际 {len(items2)}"
    # ✕ 收起：隐藏但模式保持（不再需要去设置重开）
    changed = []
    fp.mode_changed.connect(lambda v: changed.append(v))
    fp.hide_panel()
    assert not fp.isVisible(), "✕ 后面板应隐藏"
    assert fp.is_enabled(), "✕ 收起不应退出悬浮模式"
    assert changed == [], "收起不应触发模式变化"
    # 顶栏按钮：收起中 → 点击 → 显示
    win._on_float_btn()
    assert fp.isVisible(), "顶栏 ▣ 悬浮 按钮应能再显示面板"
    # 面板 🏠 召唤/收回主界面（toggle 回调）
    toggled = []
    fp._on_toggle_main = lambda: toggled.append(True)
    fp._open_main()
    assert toggled == [True], "🏠 应触发召唤/收回回调"
    print("  [OK] 10. 桌面悬浮面板：开关/大小/复制/搜索/✕收起不退出模式/顶栏一键开关/🏠召唤收回主界面")

    # --- 11. 设置不互相覆盖（v1.14 回归：用户设置主题后操作悬浮面板不得抹掉主题）---
    from config import load_settings, save_settings, update_settings
    snapshot = load_settings()
    try:
        update_settings(theme="dark")                 # 用户设置深色
        fp.set_enabled(True)                          # 动悬浮面板（旧代码会用陈旧快照整体写回）
        fp.set_enabled(False)
        s = load_settings()
        assert s.get("theme") == "dark", f"theme 被覆盖了: {s}"
        print("  [OK] 11. 设置原子更新：动悬浮面板不再抹掉 theme/其他字段")
    finally:
        save_settings(snapshot)

    win.close()
    # 收尾：清理测试创建的图片文件（全局 images 目录），不留孤儿
    image_store.remove_files(db.clear_all())
    db.close()
    os.unlink(tmp.name)
    print("== UI 冒烟测试全部通过 [OK] ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
