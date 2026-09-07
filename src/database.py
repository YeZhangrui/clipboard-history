"""SQLite 数据层（阶段 2：文本/图片入库、去重、置顶、删除、搜索、按天清理）"""
import datetime
import hashlib
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS clipboard_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT    NOT NULL,              -- 'text' | 'image'
    content        TEXT,                          -- 文本内容；图片记录为 NULL
    image_path     TEXT,                          -- 图片：原图相对路径（相对 data/）
    thumbnail_path TEXT,                          -- 图片：缩略图相对路径
    content_hash   TEXT    NOT NULL,              -- 内容指纹，去重用
    pinned         INTEGER NOT NULL DEFAULT 0,    -- 0=普通 1=置顶
    created_at     TEXT    NOT NULL,              -- 首次记录时间（本地 ISO8601，毫秒）
    updated_at     TEXT    NOT NULL               -- 最后更新时间（清理/排序依据）
);
CREATE INDEX IF NOT EXISTS idx_hash    ON clipboard_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_updated ON clipboard_items(updated_at);
CREATE INDEX IF NOT EXISTS idx_pinned  ON clipboard_items(pinned);
"""

_COLS = "id, type, content, image_path, thumbnail_path, pinned, created_at, updated_at"


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        # 微秒精度：防止短时间内连续复制导致排序不稳定
        return datetime.datetime.now().isoformat(timespec="microseconds")

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ---------- 写入 ----------

    def add_text(self, text: str) -> str:
        """文本入库；内容已存在则仅更新时间（合并，防刷屏）。返回 'inserted'/'merged'。"""
        h = self._hash_text(text)
        now = self._now()
        row = self.conn.execute(
            "SELECT id FROM clipboard_items WHERE content_hash=? AND type='text'",
            (h,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE clipboard_items SET updated_at=? WHERE id=?", (now, row[0])
            )
            self.conn.commit()
            return "merged"
        self.conn.execute(
            "INSERT INTO clipboard_items (type, content, image_path, thumbnail_path, "
            "content_hash, pinned, created_at, updated_at) "
            "VALUES ('text', ?, NULL, NULL, ?, 0, ?, ?)",
            (text, h, now, now),
        )
        self.conn.commit()
        return "inserted"

    def add_image(self, content_hash: str, image_path: str, thumbnail_path: str) -> str:
        """图片入库（文件由调用方先落盘）；已存在则仅更新时间。返回 'inserted'/'merged'。"""
        now = self._now()
        row = self.conn.execute(
            "SELECT id, image_path FROM clipboard_items WHERE content_hash=? AND type='image'",
            (content_hash,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE clipboard_items SET updated_at=? WHERE id=?", (now, row[0])
            )
            self.conn.commit()
            return "merged"
        self.conn.execute(
            "INSERT INTO clipboard_items (type, content, image_path, thumbnail_path, "
            "content_hash, pinned, created_at, updated_at) "
            "VALUES ('image', NULL, ?, ?, ?, 0, ?, ?)",
            (image_path, thumbnail_path, content_hash, now, now),
        )
        self.conn.commit()
        return "inserted"

    # ---------- 查询 ----------

    def list_items(self, limit: int = 100, type_filter: str | None = None) -> list:
        """置顶优先 + 时间降序（同时间按 id 倒序保证稳定）；可按类型过滤（'text'/'image'/None）。"""
        if type_filter in ("text", "image"):
            return self.conn.execute(
                f"SELECT {_COLS} FROM clipboard_items WHERE type=? "
                "ORDER BY pinned DESC, updated_at DESC, id DESC LIMIT ?",
                (type_filter, limit),
            ).fetchall()
        return self.conn.execute(
            f"SELECT {_COLS} FROM clipboard_items "
            "ORDER BY pinned DESC, updated_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_item(self, item_id: int):
        return self.conn.execute(
            f"SELECT {_COLS} FROM clipboard_items WHERE id=?", (item_id,)
        ).fetchone()

    def search_items(self, keyword: str, limit: int = 100, type_filter: str | None = None) -> list:
        """文本关键词搜索（忽略大小写，转义 LIKE 通配符）。
        type_filter='image' 时忽略关键词（图片不支持文本搜索），返回全部图片；
        无关键词无类型 → 返回全部记录（保持"全部"筛选语义）。"""
        if type_filter == "image":
            return self.list_items(limit, "image")
        if not keyword:
            return self.list_items(limit, type_filter)
        esc = (
            keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        like = f"%{esc}%"
        return self.conn.execute(
            f"SELECT {_COLS} FROM clipboard_items "
            "WHERE type='text' AND content LIKE ? ESCAPE '\\' "
            "ORDER BY pinned DESC, updated_at DESC, id DESC LIMIT ?",
            (like, limit),
        ).fetchall()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM clipboard_items").fetchone()[0]

    # ---------- 修改 / 删除 / 清理 ----------

    def set_pinned(self, item_id: int, pinned: int) -> bool:
        """置顶/取消置顶。返回是否找到该记录。"""
        cur = self.conn.execute(
            "UPDATE clipboard_items SET pinned=? WHERE id=?", (1 if pinned else 0, item_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_item(self, item_id: int) -> list:
        """删除单条记录。返回被删行的图片路径列表（供调用方删文件）。"""
        row = self.conn.execute(
            "SELECT image_path, thumbnail_path FROM clipboard_items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not row:
            return []
        self.conn.execute("DELETE FROM clipboard_items WHERE id=?", (item_id,))
        self.conn.commit()
        return [row[0], row[1]]

    def cleanup_expired(self, keep_days: int) -> list:
        """清理过期记录（置顶的不清理）。返回被删行的图片路径列表（供调用方删文件）。"""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=keep_days)).isoformat(
            timespec="microseconds"
        )
        rows = self.conn.execute(
            "SELECT id, image_path, thumbnail_path FROM clipboard_items "
            "WHERE pinned=0 AND updated_at < ?",
            (cutoff,),
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        self.conn.executemany("DELETE FROM clipboard_items WHERE id=?", [(i,) for i in ids])
        self.conn.commit()
        paths = []
        for _i, img_path, thumb_path in rows:
            paths.extend([img_path, thumb_path])
        return paths

    def clear_all(self) -> list:
        """清空全部记录（含置顶）。返回图片路径列表（供调用方删文件）。"""
        rows = self.conn.execute(
            "SELECT image_path, thumbnail_path FROM clipboard_items"
        ).fetchall()
        self.conn.execute("DELETE FROM clipboard_items")
        self.conn.commit()
        paths = []
        for img_path, thumb_path in rows:
            paths.extend([img_path, thumb_path])
        return paths

    def clear_unpinned(self) -> list:
        """清空所有未置顶记录（置顶保留）。返回图片路径列表（供调用方删文件）。"""
        rows = self.conn.execute(
            "SELECT image_path, thumbnail_path FROM clipboard_items WHERE pinned=0"
        ).fetchall()
        self.conn.execute("DELETE FROM clipboard_items WHERE pinned=0")
        self.conn.commit()
        paths = []
        for img_path, thumb_path in rows:
            paths.extend([img_path, thumb_path])
        return paths

    def close(self):
        self.conn.close()
