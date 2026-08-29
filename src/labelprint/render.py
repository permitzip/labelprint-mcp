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


def _block_height(
    lines: list[str], font: ImageFont.ImageFont, gap: int
) -> int:
    if not lines:
        return 0
    return sum(_measure(font, line)[1] for line in lines) + gap * max(0, len(lines) - 1)


def _ink_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Inclusive-left / exclusive-right PIL bbox of ink (pixels darker than 128)."""
    return image.point(lambda p: 255 if p < 128 else 0).getbbox()


def _draw_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    gap: int,
    top: int,
    left: int,
    area_w: int,
    *,
    align: str = "center",
) -> None:
    y = top
    for line in lines:
        w, h = _measure(font, line)
        bbox = font.getbbox(line)
        if align == "left":
            x = left
        else:
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


def _fit_chunks(
    chunks: list[tuple[str, bool]],
    text_w: int,
    text_h: int,
) -> list[tuple[list[str], ImageFont.ImageFont, int, int]]:
    fitted: list[tuple[list[str], ImageFont.ImageFont, int, int]] = []
    leftover = text_h
    for i, (text, bold) in enumerate(chunks):
        share = leftover if i == len(chunks) - 1 else max(24, int(leftover * 0.65))
        lines, font, gap = _fit_wrapped(
            text, text_w, share, bold=bold, max_size=28 if bold else 18, min_size=11
        )
        block_h = _block_height(lines, font, gap)
        fitted.append((lines, font, gap, block_h))
        leftover = max(20, leftover - block_h - 8)
    return fitted


def _stack_image(
    fitted: list[tuple[list[str], ImageFont.ImageFont, int, int]],
    *,
    width: int,
    align: str,
    stack_gap: int = 8,
) -> Image.Image:
    height = sum(block_h for *_, block_h in fitted) + stack_gap * max(0, len(fitted) - 1)
    pad = 8
    img = Image.new("L", (max(1, width) + pad * 2, max(1, height) + pad * 2), 255)
    draw = ImageDraw.Draw(img)
    y = pad
    for lines, font, gap, block_h in fitted:
        _draw_block(draw, lines, font, gap, y, pad, width, align=align)
        y += block_h + stack_gap
    return img


def _slide_ink(img: Image.Image, *, dx: int = 0, dy: int = 0) -> Image.Image:
    """Move every inked pixel by (dx, dy), clipped so the crop stays on canvas."""
    box = _ink_bbox(img)
    if box is None or (dx == 0 and dy == 0):
        return img
    crop = img.crop(box)
    out = Image.new("L", img.size, 255)
    x = max(0, min(img.width - crop.width, box[0] + dx))
    y = max(0, min(img.height - crop.height, box[1] + dy))
    out.paste(crop, (x, y))
    return out


def _paste_ink(
    dest: Image.Image,
    src: Image.Image,
    *,
    region: tuple[int, int, int, int],
    h_align: str,
) -> None:
    """Paste src's ink bbox into *region* (l, t, r, b exclusive), vertically centered."""
    box = _ink_bbox(src)
    if box is None:
        return
    crop = src.crop(box)
    left, top, right, bottom = region
    avail_w = max(1, right - left)
    avail_h = max(1, bottom - top)
    x = left if h_align == "left" else left + max(0, (avail_w - crop.width) // 2)
    y = top + max(0, (avail_h - crop.height) // 2)
    dest.paste(crop, (x, y))


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
    qr_ink_right = margin
    if qr:
        side = min(height_px - 2 * margin, width_px // 3)
        qr_img = _qr_image(qr, side)
        qr_img = qr_img.resize((side, side), Image.Resampling.NEAREST)
        qx, qy = margin, (height_px - side) // 2
        img.paste(qr_img, (qx, qy))
        qr_box = _ink_bbox(qr_img)
        qr_ink_right = qx + (qr_box[2] if qr_box else side)

    gutter = max(8, margin // 2)
    text_left = qr_ink_right + gutter if qr_img is not None else margin
    # Extra air on the right so a full-width wrap cannot hug the tape edge.
    text_right = width_px - (margin + gutter if qr_img is not None else margin)
    text_w = max(8, text_right - text_left)

    rule_y = height_px // 2
    clear = 10
    if title and body and not qr:
        title_lines, title_font, title_gap = _fit_wrapped(
            title, text_w, rule_y - margin - clear, bold=True, max_size=36, min_size=12
        )
        body_lines, body_font, body_gap = _fit_wrapped(
            body, text_w, height_px - rule_y - margin - clear, bold=False, max_size=20, min_size=11
        )
        title_h = _block_height(title_lines, title_font, title_gap)
        body_h = _block_height(body_lines, body_font, body_gap)
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
        if chunks:
            text_h = height_px - 2 * margin
            fitted = _fit_chunks(chunks, text_w, text_h)
            align = "left" if qr_img is not None else "center"
            stack = _stack_image(fitted, width=text_w, align=align)
            _paste_ink(
                img,
                stack,
                region=(text_left, margin, text_right, height_px - margin),
                h_align=align,
            )
    if qr_img is not None:
        # 384-dot heads sit on the right of 50 mm (~400 px) tape, and this
        # printer still lands a hair further right. Slide the finished QR+text
        # group left so the physical sticker looks centered.
        img = _slide_ink(img, dx=-10)
    return img
