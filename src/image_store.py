"""图片存储：落盘、缩略图、读取、删除（阶段 2）"""
import hashlib
import os

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from config import get_data_dir, get_images_dir

THUMB_SIZE = 256  # 缩略图最长边（px）


def image_to_png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


FINGERPRINT_SIZE = 64  # 指纹缩略图边长（px）


def fingerprint(img: QImage) -> str:
    """图片内容指纹（去重用）。

    缩放到 64px 标准尺寸后对归一化 ARGB32 像素做 sha256：
    - 同一张图无论从哪个程序复制、何种格式解码、何种分辨率，像素一致即视为同一张；
    - 缩放会抹平解码/预乘 alpha 等微小差异，对"软件自身往返"（保存→读取→剪贴板→再捕获）稳定。
    """
    thumb = img.scaled(
        FINGERPRINT_SIZE, FINGERPRINT_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    norm = thumb.convertToFormat(QImage.Format.Format_ARGB32)
    data = bytes(norm.constBits())
    return hashlib.sha256(data).hexdigest()


def save_image(img: QImage) -> tuple:
    """保存原图 + 缩略图。返回 (hash, 原图相对路径, 缩略图相对路径)，相对 data/ 目录。"""
    h = fingerprint(img)
    rel = f"images/{h}.png"
    thumb_rel = f"images/thumb_{h}.png"
    get_images_dir()  # 确保 images/ 目录存在
    full = os.path.join(get_data_dir(), rel)
    thumb_full = os.path.join(get_data_dir(), thumb_rel)

    if not os.path.exists(full):
        if not img.save(full, "PNG"):
            raise OSError(f"图片保存失败: {full}")
    if not os.path.exists(thumb_full):
        thumb = img.scaled(
            THUMB_SIZE, THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not thumb.save(thumb_full, "PNG"):
            raise OSError(f"缩略图保存失败: {thumb_full}")
    return h, rel, thumb_rel


def load_image(rel_path: str) -> QImage:
    img = QImage()
    img.load(os.path.join(get_data_dir(), rel_path))
    return img


def remove_files(rel_paths: list) -> None:
    """删除数据库里引用的图片文件（容错：文件不存在忽略）"""
    if not rel_paths:
        return
    for p in rel_paths:
        if not p:
            continue
        full = os.path.join(get_data_dir(), p)
        try:
            os.remove(full)
        except OSError:
            pass
