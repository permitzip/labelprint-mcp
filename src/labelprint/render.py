"""Render a simple title / body / optional QR label to a 1-bit PNG."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from labelprint.errors import ImageError

FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = FONT_CANDIDATES
    if bold:
        preferred = [p for p in names if "Bold" in p.name or "bold" in p.name]
        names = (*preferred, *names)
    for path in names:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _measure(font: ImageFont.ImageFont, text: str) -> tuple[int, int]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if _measure(font, trial)[0] <= max_w:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    gap: int,
    top: int,
    left: int,
    area_w: int,
) -> None:
    y = top
    for line in lines:
        w, h = _measure(font, line)
        bbox = font.getbbox(line)
        x = left + (area_w - w) // 2
        draw.text((x - bbox[0], y - bbox[1]), line, fill=0, font=font)
        y += h + gap


def _fit_wrapped(
    text: str,
    max_w: int,
    max_h: int,
    *,
    bold: bool,
    max_size: int,
    min_size: int,
) -> tuple[list[str], ImageFont.ImageFont, int]:
    for size in range(max_size, min_size - 1, -1):
        font = _font(size, bold=bold)
        lines = _wrap(text, font, max_w)
        if len(lines) > 5:
            continue
        gap = max(2, int(size * 0.2))
        height = sum(_measure(font, line)[1] for line in lines) + gap * max(0, len(lines) - 1)
        if height <= max_h and max(_measure(font, line)[0] for line in lines) <= max_w:
            return lines, font, gap
    font = _font(min_size, bold=bold)
    return _wrap(text, font, max_w), font, 2


def _qr_image(payload: str, box: int) -> Image.Image:
    try:
        import segno
    except ImportError as exc:
        raise ImageError(
            "QR rendering needs the optional extra: pip install 'labelprint[qr]'"
        ) from exc
    qr = segno.make(payload, error="m")
    scale = max(1, box // max(qr.symbol_size()[0], 1))
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=1)
    buf.seek(0)
    return Image.open(buf).convert("L")


def render_label(
    *,
    width_px: int,
    height_px: int,
    title: str | None = None,
    body: str | None = None,
    qr: str | None = None,
) -> Image.Image:
    if width_px < 32 or height_px < 32:
        raise ImageError("label canvas is too small")
    img = Image.new("L", (width_px, height_px), 255)
    draw = ImageDraw.Draw(img)
    margin = max(8, min(width_px, height_px) // 16)
    qr_img = None
    text_left = margin
    text_w = width_px - 2 * margin
    if qr:
        side = min(height_px - 2 * margin, width_px // 3)
        qr_img = _qr_image(qr, side)
        qr_img = qr_img.resize((side, side), Image.Resampling.NEAREST)
        img.paste(qr_img, (margin, (height_px - side) // 2))
        text_left = margin + side + margin // 2
        text_w = width_px - text_left - margin

    rule_y = height_px // 2
    clear = 10
    if title and body and not qr:
        title_lines, title_font, title_gap = _fit_wrapped(
            title, text_w, rule_y - margin - clear, bold=True, max_size=36, min_size=12
        )
        body_lines, body_font, body_gap = _fit_wrapped(
            body, text_w, height_px - rule_y - margin - clear, bold=False, max_size=20, min_size=11
        )
        title_h = sum(_measure(title_font, line)[1] for line in title_lines) + title_gap * max(
            0, len(title_lines) - 1
        )
        body_h = sum(_measure(body_font, line)[1] for line in body_lines) + body_gap * max(
            0, len(body_lines) - 1
        )
        _draw_block(
            draw,
            title_lines,
            title_font,
            title_gap,
            margin + (rule_y - clear - margin - title_h) // 2,
            text_left,
            text_w,
        )
        draw.line(
            [(text_left + 8, rule_y), (text_left + text_w - 8, rule_y)],
            fill=0,
            width=2,
        )
        _draw_block(
            draw,
            body_lines,
            body_font,
            body_gap,
            rule_y + clear + (height_px - margin - rule_y - clear - body_h) // 2,
            text_left,
            text_w,
        )
    else:
        chunks: list[tuple[str, bool]] = []
        if title:
            chunks.append((title, True))
        if body:
            chunks.append((body, False))
        if not chunks and qr_img is None:
            raise ImageError("render needs title, body, or qr")
        y = margin
        remaining = height_px - 2 * margin
        for i, (text, bold) in enumerate(chunks):
            share = remaining // max(1, len(chunks) - i)
            lines, font, gap = _fit_wrapped(
                text, text_w, share, bold=bold, max_size=28 if bold else 18, min_size=11
            )
            _draw_block(draw, lines, font, gap, y, text_left, text_w)
            block_h = sum(_measure(font, line)[1] for line in lines) + gap * max(0, len(lines) - 1)
            y += block_h + 8
    return img
