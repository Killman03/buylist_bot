"""
Легковесный заменитель стандартного модуля imghdr, удалённого в Python 3.13.
Нужен для совместимости с PaddleOCR (импортирует imghdr напрямую).
Основано на реализации из стандартной библиотеки Python 3.11.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Iterable, Optional, Tuple


def what(file: str | bytes | BinaryIO | None, h: bytes | None = None) -> Optional[str]:
    """
    Определяет тип изображения по сигнатуре.

    Args:
        file: путь/файл/байты
        h: необязательный заранее прочитанный буфер
    """
    if h is None:
        if hasattr(file, "read"):
            f = file  # type: ignore[assignment]
            pos = f.tell()
            h = f.read(32)
            f.seek(pos)
        else:
            with open(file, "rb") as f:  # type: ignore[arg-type]
                h = f.read(32)

    for name, test in _tests:
        if test(h):
            return name
    return None


def _test_jpeg(h: bytes) -> bool:
    return h[:3] == b"\xff\xd8\xff"


def _test_png(h: bytes) -> bool:
    return h[:8] == b"\x89PNG\r\n\x1a\n"


def _test_gif(h: bytes) -> bool:
    return h[:6] in (b"GIF87a", b"GIF89a")


def _test_webp(h: bytes) -> bool:
    return len(h) >= 12 and h[:4] == b"RIFF" and h[8:12] == b"WEBP"


def _test_bmp(h: bytes) -> bool:
    return h[:2] == b"BM"


def _test_tiff(h: bytes) -> bool:
    return h[:4] in (b"MM\x00*", b"II*\x00")


def _test_pbm(h: bytes) -> bool:
    return h[:2] == b"P1"


def _test_pgm(h: bytes) -> bool:
    return h[:2] == b"P2"


def _test_ppm(h: bytes) -> bool:
    return h[:2] == b"P3"


def _test_pam(h: bytes) -> bool:
    return h[:2] == b"P7"


def _test_pnm(h: bytes) -> bool:
    return h[:2] == b"P5" or h[:2] == b"P6"


def _test_rast(h: bytes) -> bool:
    return h[:4] == b"\x59\xA6\x6A\x95"


def _test_sgi(h: bytes) -> bool:
    return h[:2] == b"\x01\xda"


def _test_exr(h: bytes) -> bool:
    return h[:4] == b"\x76\x2f\x31\x01"


def _test_blf(h: bytes) -> bool:
    return h[:7] == b"BLENDER"


_tests: Iterable[Tuple[str, callable]] = (
    ("jpeg", _test_jpeg),
    ("png", _test_png),
    ("gif", _test_gif),
    ("webp", _test_webp),
    ("bmp", _test_bmp),
    ("tiff", _test_tiff),
    ("rast", _test_rast),
    ("sgi", _test_sgi),
    ("pbm", _test_pbm),
    ("pgm", _test_pgm),
    ("ppm", _test_ppm),
    ("pam", _test_pam),
    ("pnm", _test_pnm),
    ("exr", _test_exr),
    ("blender", _test_blf),
)
