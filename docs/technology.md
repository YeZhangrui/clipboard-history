# 技术方案 — 剪贴板历史 v1.0

> 文档编号：TECH-001　|　版本：v1.0　|　状态：已定稿（2026-09-07）

## 1. 技术选型

| 环节 | 选型 | 理由 |
|---|---|---|
| 语言 / GUI | Python 3.11 + PySide6 (Qt6) | 剪贴板监听（`QClipboard.dataChanged`）天然支持文本与图片双类型；托盘（`QSystemTrayIcon`）、SQL 窗口组件齐全；开发迭代快、生态成熟 |
| 数据存储 | SQLite（Python 内置标准库） | 零安装、单文件数据库，万亿级顺序读写无压力；支持索引与事务 |
| 图片存储 | 文件系统 `data/images/`，数据库存路径 | 避免数据库膨胀，便于预览与清理 |
| 配置存储 | JSON 文件 `data/config.json` | 人类可读、便于调试（存储天数、开机自启开关） |
| 打包 | PyInstaller `--onefile` | 产出单个 exe，满足免安装交付 |
| 开机自启 | 注册表 `HKCU\...\Run` | 用户级启动项，无需管理员权限 |
| 单实例 | `QLockFile` | 防止多进程同时写数据库 |

> 说明：开发过程在本机进行；最终用户**无需安装 Python**，拿到 exe 即可使用。

## 2. 整体架构

```
[系统剪贴板] ──dataChanged──> [监听过任务] ──write──> [SQLite 数据库]
                                  |                        |
                                  v                        v
                            [图片落盘 data/images]    [按天数清理任务(定时)]
                                                     
[托盘图标] <──控制── [Qt 主窗口] ──query──> [数据库读取层]
    |                                                    |
    +──右键菜单：打开/退出、设置                              v
    +──开机自启(注册表)                                  [UI 列表/搜索/置顶/删除]
```

- **后台常驻**：进程常驻托盘；主窗口可关闭（仅隐藏）。
- **单向数据流**：剪贴板 → 数据库 → UI。UI 只读展示，删除/置顶通过 SQL 操作。

## 3. 目录结构

```
粘贴板历史/
├── README.md                    # 项目总指南（本文件索引）
├── docs/                        # 项目文档体系
│   ├── requirements.md          # 需求规格说明书
│   ├── technology.md            # 技术方案（本文件）
│   ├── design.md                # UI/UX 设计规范
│   ├── development-plan.md      # 开发执行计划（分阶段）
│   └── devlog-convention.md     # 开发日志书写规范
├── devlogs/                     # 开发日志（每日一个 md 文件）
├── src/                         # 源代码（开发阶段创建）
│   ├── main.py                  # 入口：单实例 → 启动监听 → 显示窗口/托盘
│   ├── clipboard_watcher.py     # 剪贴板监听、去重、图片落盘
│   ├── database.py              # SQLite 读写层（增删查、清理、置顶）
│   ├── ui/                      # Qt 界面
│   │   ├── main_window.py       # 主窗口（顶栏/列表/搜索/清空）
│   │   ├── item_card.py         # 记录卡片（文本/图片、置顶、删除、点击复制）
│   │   ├── settings_dialog.py   # 设置对话框（开机自启、存储期限、数据位置说明）
│   │   └── style.py             # 主题样式（QSS、应用图标、搜索图标）
│   ├── tray.py                  # 托盘图标与菜单
│   ├── autostart.py             # 开机自启（注册表）
│   └── config.py                # 配置读写
├── data/                        # 运行时生成：数据库 + 图片 + 配置（随 exe 同目录）
└── 打包脚本/ build.bat          # 打包为单个 exe 的脚本（后期阶段创建）
```

## 4. 数据库设计

表：`clipboard_items`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| type | TEXT | `text` / `image` |
| content | TEXT | 文本记录的内容；图片记录为 NULL |
| image_path | TEXT | 图片记录：相对路径（`data/images/` 下） |
| thumbnail_path | TEXT | 图片记录：缩略图相对路径 |
| content_hash | TEXT | 内容指纹（文本 Hash / 图片 Hash），用于去重合并 |
| pinned | INTEGER | 0=普通，1=置顶 |
| created_at | TEXT | 首次记录时间（ISO8601） |
| updated_at | TEXT | 最后更新时间（ISO8601），清理按此计算 |

索引：`content_hash`（去重）、`updated_at`（清理与排序）、`pinned`（置顶过滤）。

## 5. 关键实现要点

1. **监听**：`QClipboard.dataChanged` 信号；文本取 `QClipboard.text()`，图片取 `QClipboard.image()`；
   剪贴板只保留"最近状态"，因此监听回调里必须**同步落库**，防止后续复制覆盖。
2. **去重**：对内容计算 `sha256`；已存在且未置顶的记录 → 仅更新 `updated_at`（重置存储期限）；
   若用户确实想存两份，允许其先置顶旧记录（v1.0 采用合并策略，界面提示）。
3. **图片落盘**：原始图片存 `data/images/`，PNG 格式保存；缩略图（约 256px）供列表显示，降低内存。
4. **清理任务**：进程内定时器每 10 分钟执行一次
   `DELETE FROM clipboard_items WHERE pinned=0 AND updated_at < now - 存储天数`。
5. **点击再复制**：文本 → `QClipboard.setText`；图片 → 从磁盘读取并 `setImage`。
6. **单实例**：`QLockFile("data/app.lock")` 锁定失败则发送信号唤醒已有窗口并退出。
7. **异常兜底**：任何监听/写库异常只记日志，不崩溃、不影响用户复制。

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 剪贴板被其他软件高频修改 | 去重 + 合并更新，避免刷屏 |
| 图片过多占用磁盘 | v1.0 原图保存 + 缩略图；后续版本加容量上限与压缩 |
| 打包后 exe 被杀毒软件误报 | PyInstaller 使用常规参数；如遇误报提供改机方案或改用安装包 |
| 数据库损坏 | 定期自检（`PRAGMA integrity_check`），损坏时重建并保留旧文件 |
