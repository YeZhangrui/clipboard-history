"""生成应用图标 icon.ico（Windows ICO 容器内嵌 PNG，Vista+ 支持）"""
import os
import struct

from PySide6.QtCore import QBuffer, QIODevice, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

SIZES = [16, 32, 48, 256]


def _make_png(size: int) -> bytes:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#4A90D9"))
    p.setPen(Qt.PenStyle.NoPen)
    r = size / 64.0
    p.drawRoundedRect(QRect(int(4 * r), int(4 * r), int(56 * r), int(56 * r)), int(14 * r), int(14 * r))
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(QRect(int(18 * r), int(17 * r), int(28 * r), int(33 * r)), int(5 * r), int(5 * r))
    p.setBrush(QColor("#4A90D9"))
    p.drawRoundedRect(QRect(int(24 * r), int(12 * r), int(16 * r), int(9 * r)), int(4 * r), int(4 * r))
    p.drawRoundedRect(QRect(int(25 * r), int(26 * r), int(14 * r), int(3 * r)), int(1 * r), int(1 * r))
    p.drawRoundedRect(QRect(int(25 * r), int(33 * r), int(14 * r), int(3 * r)), int(1 * r), int(1 * r))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def main():
    pngs = [(s, _make_png(s)) for s in SIZES]
    # ICO 头 + 每项 16 字节描述 + PNG 数据
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries = b""
    blobs = b""
    for size, data in pngs:
        w = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open("icon.ico", "wb") as f:
        f.write(header + entries + blobs)
    print("icon.ico written,", os.path.getsize("icon.ico"), "bytes")


if __name__ == "__main__":
    main()
