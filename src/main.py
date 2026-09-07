"""剪贴板历史 — 程序入口（阶段 3）

用法:
    python src/main.py                         启动主窗口（后台监听 + 界面）
    python src/main.py --dump [N]              打印最近 N 条记录（默认 10）
    python src/main.py --search 关键词          搜索文本记录
    python src/main.py --pin ID                置顶 / --unpin ID 取消置顶
    python src/main.py --delete ID             删除单条记录
    python src/main.py --cleanup               立即执行一次过期清理
    python src/main.py --storage-days N        设置存储天数（1/3/5）
    python src/main.py --self-test             自动化自测
    python src/main.py --listen-seconds S      监听 S 秒后自动退出（测试用）
"""
import argparse
import os
import signal
import sys
import tempfile
import time

# 控制台编码兜底（Windows 默认 GBK，遇到特殊符号会崩溃）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import autostart
import image_store
from clipboard_watcher import ClipboardWatcher
from config import get_data_dir, get_db_path, load_settings, save_settings
from database import Database
from theme import ThemeManager
from tray import TrayManager
from ui.main_window import MainWindow
from ui.style import make_app_icon

CLEANUP_INTERVAL_MS = 10 * 60 * 1000  # 每 10 分钟清理一次过期内容
SERVER_NAME = "clipboard-history-app"  # 单实例唤醒通道（QLocalServer 名）


def summarize(text: str, width: int = 80) -> str:
    t = " ".join(text.split())
    return t if len(t) <= width else t[: width - 1] + "..."


def _fmt_row(row) -> str:
    rid, typ, content, _img, _thumb, pinned, created, updated = row
    mark = "[置顶]" if pinned else "      "
    if typ == "text":
        body = summarize(content) if content else ""
        return f"[#{rid}] {mark} {updated}  {body}"
    return f"[#{rid}] {mark} {updated}  [图片]"


def cmd_dump(db: Database, limit: int):
    items = db.list_items(limit)
    if not items:
        print("（暂无记录）")
        return
    print(f"共 {db.count()} 条记录，最近 {len(items)} 条：")
    for i, row in enumerate(items, 1):
        print(f"{i:>3}. {_fmt_row(row)}")


def cmd_search(db: Database, keyword: str, limit: int = 20):
    items = db.search_items(keyword, limit)
    if not items:
        print(f"未找到包含 “{keyword}” 的记录")
        return
    print(f"找到 {len(items)} 条包含 “{keyword}” 的记录：")
    for i, row in enumerate(items, 1):
        print(f"{i:>3}. {_fmt_row(row)}")


def do_cleanup(db: Database) -> int:
    """执行过期清理（含删除过期图片文件），返回删除条数。"""
    keep_days = load_settings().get("storage_days", 3)
    paths = db.cleanup_expired(keep_days)
    image_store.remove_files(paths)
    n = len(paths) // 2  # 每条图片记录对应 2 个路径（png + thumb）
    return n


def cmd_set_storage_days(days: int):
    s = load_settings()
    s["storage_days"] = days
    save_settings(s)
    print(f"存储期限已设置为 {days} 天")


def run_self_test() -> int:
    """自动化自测：文本/图片入库、去重合并、置顶、搜索、过期清理、删除。
    使用临时数据库（绝不触碰真实用户数据）。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(tmp.name)
    try:
        return _run_self_test_impl(db)
    finally:
        db.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _run_self_test_impl(db: Database) -> int:
    print("== 自测开始 ==")

    # 清空（含自测上次的图片文件）
    image_store.remove_files(db.clear_all())

    # --- 1. 文本入库 + 去重合并 ---
    samples = [
        "这是一段测试文字：你好，剪贴板历史。",
        "第二条测试内容：数字 12345",
        "第三条测试内容：今晚吃火锅 ？",
    ]
    for s in samples:
        time.sleep(0.01)  # 模拟真实复制的间隔
        r = db.add_text(s)
        assert r == "inserted", f"新文字应插入，实际: {r}"
    assert db.count() == 3, f"应有 3 条文本，实际 {db.count()}"
    time.sleep(0.01)
    r = db.add_text(samples[1])
    assert r == "merged", f"重复文字应合并，实际: {r}"
    assert db.count() == 3, f"合并后应仍 3 条，实际 {db.count()}"
    first = db.list_items(1)[0]
    assert first[2] == samples[1], "合并后该记录应排在最前"
    print("  [OK] 1. 文本入库 + 去重合并（3 条，重复复制合并为 1 条）")

    # --- 2. 图片入库 + 去重合并 ---
    img1 = QImage(120, 80, QImage.Format.Format_RGB32)
    img1.fill(0x4A90D9FF)  # 淡蓝色
    img2 = QImage(60, 60, QImage.Format.Format_RGB32)
    img2.fill(0xE35D5DFF)  # 红色
    h1, rel1, thumb1 = image_store.save_image(img1)
    h2, rel2, thumb2 = image_store.save_image(img2)
    r = db.add_image(h1, rel1, thumb1)
    assert r == "inserted"
    r = db.add_image(h2, rel2, thumb2)
    assert r == "inserted"
    # 重复复制同一张图（同一来源）→ 合并
    h1b, rel1b, thumb1b = image_store.save_image(img1)
    assert h1b == h1, "同图指纹应一致"
    r = db.add_image(h1b, rel1b, thumb1b)
    assert r == "merged", f"重复图片应合并，实际: {r}"
    # 不同解码来源的同一张图（像素相同、对象不同）→ 指纹一致并合并（模拟从不同程序复制同一图）
    img1_again = QImage.fromData(image_store.image_to_png_bytes(img1), "PNG")
    assert not img1_again.isNull(), "PNG 重新解码失败"
    h1c = image_store.fingerprint(img1_again)
    assert h1c == h1, "同像素不同解码来源的图片指纹应一致"
    r = db.add_image(h1c, rel1, thumb1)
    assert r == "merged", f"跨来源同像素图片应合并，实际: {r}"
    # 软件自身往返（落盘 → 读回 → 再入库，等于"点击卡片复制原图"路径）→ 指纹一致并合并
    reloaded = image_store.load_image(rel1)
    assert not reloaded.isNull(), "读取落盘图片失败"
    h1d = image_store.fingerprint(reloaded)
    assert h1d == h1, "落盘读回的图片指纹应一致（往返稳定）"
    r = db.add_image(h1d, rel1, thumb1)
    assert r == "merged", f"自身往返图片应合并，实际: {r}"
    assert db.count() == 5, f"应有 5 条（3 文本 + 2 图片），实际 {db.count()}"
    # 文件确实落盘
    from config import get_data_dir
    import os
    assert os.path.exists(os.path.join(get_data_dir(), rel1))
    assert os.path.exists(os.path.join(get_data_dir(), thumb1))
    print("  [OK] 2. 图片入库 + 去重合并（原图/缩略图落盘，重复图片合并）")

    # --- 3. 置顶 ---
    img_row = [r for r in db.list_items(50) if r[1] == "image"][0]
    assert db.set_pinned(img_row[0], 1), "置顶应成功"
    top = db.list_items(1)[0]
    assert top[0] == img_row[0], "置顶后应排在最前"
    print("  [OK] 3. 置顶（置顶记录排列表最前）")

    # --- 4. 搜索 ---
    found = db.search_items("火锅")
    assert len(found) == 1 and "火锅" in found[0][2], f"应搜到火锅记录，实际 {len(found)}"
    found2 = db.search_items("不存在的内容xyz")
    assert len(found2) == 0, "搜不到时应为空"
    print("  [OK] 4. 搜索（关键词命中，通配符安全）")

    # --- 5. 过期清理：置顶的不删 ---
    old_time = "2020-01-01T00:00:00.000"
    pinned_id = img_row[0]

    # 找一条文本记录改旧（普通）
    text_row = [r for r in db.list_items(50) if r[1] == "text"][0]
    db.conn.execute("UPDATE clipboard_items SET updated_at=? WHERE id=?", (old_time, text_row[0]))
    # 把置顶的图片记录也改旧
    db.conn.execute("UPDATE clipboard_items SET updated_at=? WHERE id=?", (old_time, pinned_id))
    db.conn.commit()

    n = do_cleanup(db)  # 默认 3 天
    assert db.get_item(text_row[0]) is None, "普通过期记录应被清理"
    assert db.get_item(pinned_id) is not None, "置顶过期记录不应被清理"
    assert n == 1, f"应清理 1 条，实际 {n}"
    print("  [OK] 5. 过期清理（普通过期记录删除；置顶记录保留）")

    # --- 6. 类型检索（全部/文本/图片）---
    texts = db.list_items(50, "text")
    imgs = db.list_items(50, "image")
    assert texts and all(r[1] == "text" for r in texts), "仅文本筛选应全是文本"
    assert imgs and all(r[1] == "image" for r in imgs), "仅图片筛选应全是图片"
    img_any = db.search_items("不存在的关键词", 50, "image")
    assert all(r[1] == "image" for r in img_any), "图片类型 + 关键词应返回全部图片"
    print("  [OK] 6. 类型检索（文本/图片过滤；图片忽略关键词返回全部图片）")

    # --- 7. 删除单条 + 清空 ---
    sample = db.list_items(1)[0]
    paths = db.delete_item(sample[0])
    image_store.remove_files(paths)
    assert db.get_item(sample[0]) is None, "删除后应查不到"
    print("  [OK] 7. 删除单条记录")

    # 收尾：清空测试数据，恢复干净状态
    leftover = db.clear_all()
    image_store.remove_files(leftover)
    print("== 自测全部通过 [OK] ==（测试数据已清空）")
    return 0


def cmd_listen(db: Database, app: QApplication, listen_seconds: int):
    # Ctrl+C（SIGINT）在 Qt 事件循环中不总是立即生效，用标志位 + 定时器兜底
    stop_flag = {"v": False}
    signal.signal(signal.SIGINT, lambda *_: stop_flag.__setitem__("v", True))

    def on_record(kind, result, summary):
        tag = {"text": "文本", "image": "图片"}[kind]
        label = "新记录" if result == "inserted" else "合并更新"
        body = summarize(summary, 60) if kind == "text" else "(缩略图已保存)"
        print(f"[{db._now()}] {tag} {label}: {body}", flush=True)

    watcher = ClipboardWatcher(app, db, on_record=on_record)
    _ = watcher  # 保持引用，防止被 GC 导致信号断开

    # 启动时清理一次 + 定期清理
    n = do_cleanup(db)
    if n:
        print(f"[清理] 已清理 {n} 条过期记录", flush=True)
    cleanup_timer = QTimer()

    def periodic_cleanup():
        cleaned = do_cleanup(db)
        if cleaned:
            print(f"[清理] 清理了 {cleaned} 条过期记录", flush=True)

    cleanup_timer.timeout.connect(periodic_cleanup)
    cleanup_timer.start(CLEANUP_INTERVAL_MS)

    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if stop_flag["v"] else None)
    timer.start(300)

    print(f"已开始监听剪贴板（Ctrl+C 退出；数据文件：{get_db_path()}）", flush=True)
    if listen_seconds:
        QTimer.singleShot(listen_seconds * 1000, app.quit)
        print(f"（{listen_seconds} 秒后自动退出）", flush=True)
    app.exec()


def wake_existing() -> None:
    """第二实例发现已有进程：通过本地通道请求主实例弹出窗口，然后退出。"""
    try:
        sock = QLocalSocket()
        sock.connectToServer(SERVER_NAME)
        if sock.waitForConnected(300):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(200)
        sock.disconnectFromServer()
    except Exception:
        pass


def run_ui(db: Database, app: QApplication) -> None:
    """主界面模式：窗口 + 后台监听 + 托盘 + 定时清理 + 单实例（阶段 4）"""
    # ---- 单实例：已有进程则唤起其窗口，本进程退出 ----
    lock = QLockFile(os.path.join(get_data_dir(), "app.lock"))
    if not lock.tryLock(100):
        wake_existing()
        print("剪贴板历史已在运行：已唤起已有窗口，本次启动退出。")
        return

    app.setQuitOnLastWindowClosed(False)  # 关闭窗口=隐藏到托盘，不退出
    app.setWindowIcon(make_app_icon())

    # 主题：浅色/深色/跟随系统（设置中切换，运行中热切换）
    theme_manager = ThemeManager(app)
    theme_manager.apply()

    win = MainWindow(db, app.clipboard())
    win.set_theme_manager(theme_manager)
    win.show()

    # 监听剪贴板（窗口早于监听创建，刷新即时有目标）
    watcher = ClipboardWatcher(app, db, on_record=win.on_record_hook)
    win.set_watcher(watcher)

    # 托盘：菜单（打开/开机自启/悬浮模式/退出）+ 双击唤起 + 关闭隐藏气泡
    settings = load_settings()
    tray = TrayManager(app, win, settings)
    win.set_tray_manager(tray)

    # 桌面悬浮面板：常驻置顶（设置/托盘/顶栏一键开关；🏠 召唤/收回主界面；✕ 仅收起）
    from ui.float_panel import FloatPanel

    def toggle_main():
        """主界面显示→收回（隐藏到托盘）；隐藏→召唤前台。"""
        if win.isVisible() and not win.isMinimized():
            win.close()  # 触发"关闭=隐藏到托盘"
        else:
            win.open_main()

    float_panel = FloatPanel(app, db, watcher, settings=settings, on_toggle_main=toggle_main)
    win.set_float_manager(float_panel)
    tray.set_float_manager(float_panel)
    if settings.get("float_mode", False):
        float_panel.set_enabled(True)

    # 全局快捷键（可换组合；成功/失败均有气泡确认）
    #   main ：主界面 可见→最小化；隐藏/最小化→唤出（双向）
    #   float：悬浮面板 显示→隐藏；隐藏→显示（双向）
    from hotkey import HotkeyManager

    def toggle_main_by_hotkey():
        if win.isVisible() and not win.isMinimized():
            win.showMinimized()
        else:
            win.open_main()

    def toggle_float_by_hotkey():
        if float_panel.is_enabled():
            if float_panel.isVisible():
                float_panel.hide_panel()
            else:
                float_panel.refresh()
                float_panel.show()
                float_panel.raise_()
        else:
            float_panel.set_enabled(True)

    hotkey = HotkeyManager(app, callbacks={"main": toggle_main_by_hotkey, "float": toggle_float_by_hotkey})
    if hotkey.apply_from_settings():
        tray.tray.showMessage(
            "剪贴板历史",
            f"快捷键已启用\n主界面：{hotkey.current_name('main')}\n悬浮面板：{hotkey.current_name('float')}",
            QSystemTrayIcon.MessageIcon.Information, 4000)
    else:
        tray.tray.showMessage(
            "剪贴板历史",
            f"快捷键未全部生效：{hotkey.register_error_text()}\n可在设置中更换组合。",
            QSystemTrayIcon.MessageIcon.Warning, 6000)
    win.set_hotkey_manager(hotkey)

    # 开机自启：设置开启则刷新注册表命令为当前程序路径（exe 被移动后自动修正）
    if settings.get("autostart", True):
        autostart.enable()

    # 单实例唤醒通道：第二实例发来 "show" → 弹出主窗口
    server = QLocalServer()
    server.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)
    server.newConnection.connect(win.open_main)

    # 启动时清理一次 + 每 10 分钟定期清理
    cleaned = do_cleanup(db)
    if cleaned:
        win.statusBar().showMessage(f"已自动清理 {cleaned} 条过期记录", 4000)

    cleanup_timer = QTimer()

    def periodic_cleanup():
        n = do_cleanup(db)
        if n:
            win.statusBar().showMessage(f"已自动清理 {n} 条过期记录", 4000)
            win.reload()

    cleanup_timer.timeout.connect(periodic_cleanup)
    cleanup_timer.start(CLEANUP_INTERVAL_MS)

    app.exec()


def main():
    parser = argparse.ArgumentParser(description="剪贴板历史 - 阶段2 数据层")
    parser.add_argument("--dump", nargs="?", type=int, const=10, default=None,
                        help="打印最近 N 条记录后退出")
    parser.add_argument("--search", metavar="关键词", help="搜索文本记录")
    parser.add_argument("--pin", type=int, metavar="ID", help="置顶指定记录")
    parser.add_argument("--unpin", type=int, metavar="ID", help="取消置顶")
    parser.add_argument("--delete", type=int, metavar="ID", help="删除指定记录")
    parser.add_argument("--cleanup", action="store_true", help="立即执行一次过期清理")
    parser.add_argument("--storage-days", type=int, metavar="N", help="设置存储天数（1/3/5）")
    parser.add_argument("--self-test", action="store_true", help="运行自动化自测")
    parser.add_argument("--listen-seconds", type=int, default=0,
                        help="监听 N 秒后自动退出（测试用）")
    args = parser.parse_args()

    db = Database(get_db_path())

    if args.dump is not None:
        cmd_dump(db, args.dump)
        return 0
    if args.search is not None:
        cmd_search(db, args.search)
        return 0
    if args.pin is not None:
        ok = db.set_pinned(args.pin, 1)
        print(f"已置顶 #{args.pin}" if ok else f"记录 #{args.pin} 不存在")
        return 0
    if args.unpin is not None:
        ok = db.set_pinned(args.unpin, 0)
        print(f"已取消置顶 #{args.unpin}" if ok else f"记录 #{args.unpin} 不存在")
        return 0
    if args.delete is not None:
        paths = db.delete_item(args.delete)
        image_store.remove_files(paths)
        print(f"已删除 #{args.delete}")
        return 0
    if args.cleanup:
        print(f"已清理 {do_cleanup(db)} 条过期记录")
        return 0
    if args.storage_days is not None:
        cmd_set_storage_days(args.storage_days)
        return 0
    if args.self_test:
        return run_self_test()

    app = QApplication(sys.argv)
    if args.listen_seconds:
        cmd_listen(db, app, args.listen_seconds)
        return 0
    run_ui(db, app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
