"""Prepare 1-bit label bitmaps. Dark pixels become ink bits (1)."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from labelprint.errors import ImageError

DEFAULT_DPI = 203
MM_PER_INCH = 25.4


def mm_to_px(mm: float, dpi: int = DEFAULT_DPI) -> int:
    return max(1, int(round(mm * dpi / MM_PER_INCH)))


def load_image(path: str | Path) -> Image.Image:
    return Image.open(path)


def prepare_bitmap(
    image: Image.Image,
    *,
    max_width_px: int,
    width_px: int | None = None,
    height_px: int | None = None,
    threshold: int = 128,
) -> Image.Image:
    """Fit *image* onto a white canvas and return an ``L`` bitmap (0 ink, 255 paper)."""
    if max_width_px < 8:
        raise ImageError(f"max_width_px must be >= 8, got {max_width_px}")

    gray = image.convert("L")
    target_w = min(width_px or gray.width, max_width_px)
    target_h = height_px or gray.height
    if target_w < 1 or target_h < 1:
        raise ImageError("target size must be positive")

    fitted = gray
    if gray.width != target_w or gray.height != target_h:
        scale = min(target_w / gray.width, target_h / gray.height)
        new_w = max(1, int(round(gray.width * scale)))
        new_h = max(1, int(round(gray.height * scale)))
        fitted = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("L", (target_w, target_h), 255)
    x = (target_w - fitted.width) // 2
    y = (target_h - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas.point(lambda p: 0 if p < threshold else 255, mode="L")


def pack_row(gray: Image.Image, y: int) -> bytes:
    """Pack one scanline. Bit 1 = ink. MSB is the leftmost pixel."""
    width = gray.width
    stride = math.ceil(width / 8)
    out = bytearray(stride)
    for x in range(width):
        if gray.getpixel((x, y)) < 128:
            out[x // 8] |= 1 << (7 - (x % 8))
    return bytes(out)


def split_ink_counts(line: bytes, printhead_width: int) -> tuple[int, int, int]:
    """Split inked-bit counts into the three header buckets the printhead expects."""
    chunk = max(1, (printhead_width // 8) // 3)
    parts = [0, 0, 0]
    for i, value in enumerate(line):
        parts[min(i // chunk, 2)] += value.bit_count()
    return parts[0], parts[1], parts[2]


def encode_rows(gray: Image.Image) -> list[tuple[int, int, bytes]]:
    """Return ``(y, run, packed_row)`` runs, collapsing identical consecutive rows."""
    rows = gray.height
    encoded: list[tuple[int, int, bytes]] = []
    y = 0
    while y < rows:
        line = pack_row(gray, y)
        run = 1
        while y + run < rows and run < 200 and pack_row(gray, y + run) == line:
            run += 1
        encoded.append((y, run, line))
        y += run
    return encoded
