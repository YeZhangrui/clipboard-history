"""配置管理：路径、常量与设置读写（阶段 2）"""
import json
import os
import sys

APP_NAME = "剪贴板历史"

# 默认设置（存 data/settings.json）
DEFAULT_SETTINGS = {
    "storage_days": 3,   # 存储期限（天）：1 / 3 / 5
    "autostart": True,   # 开机自启（用户需求确认默认开启）
}

# 开发期 data 目录 = 项目根/data；打包后 = exe 同目录/data
def get_data_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return d

def get_db_path() -> str:
    return os.path.join(get_data_dir(), "clipboard.db")

def get_images_dir() -> str:
    d = os.path.join(get_data_dir(), "images")
    os.makedirs(d, exist_ok=True)
    return d

def get_settings_path() -> str:
    return os.path.join(get_data_dir(), "settings.json")

def load_settings() -> dict:
    """读取设置；文件不存在或损坏时使用默认值。"""
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(get_settings_path(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            s.update(saved)
    except (OSError, ValueError):
        pass
    return s

def save_settings(settings: dict) -> None:
    with open(get_settings_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def update_settings(**kwargs) -> dict:
    """以文件为唯一真相的原子更新：读最新 → 合并 → 写回。
    用于避免"旧快照整体写回"导致其他字段（如 theme）被抹掉（v1.14 修复）。"""
    s = load_settings()
    s.update(kwargs)
    save_settings(s)
    return s
