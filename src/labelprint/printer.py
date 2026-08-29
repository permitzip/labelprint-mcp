from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from labelprint.config import Settings, media_for_barcode
from labelprint.errors import ConfigError
from labelprint.imageutil import mm_to_px, prepare_bitmap
from labelprint.render import render_label
from labelprint.session import open_printer


def canvas_size(settings: Settings, barcode: str | None = None) -> tuple[int, int]:
    width_mm, height_mm, dpi = media_for_barcode(settings, barcode)
    if width_mm is None or height_mm is None:
        raise ConfigError(
            "set media.width_mm and media.height_mm (or pass --width-mm / --height-mm). "
            "This tool does not look up rolls on the internet."
        )
    width_px = min(settings.max_width_px, mm_to_px(width_mm, dpi))
    height_px = mm_to_px(height_mm, dpi)
    return width_px, height_px


def prepare_for_print(
    image: Image.Image, settings: Settings, barcode: str | None = None
) -> Image.Image:
    try:
        width_px, height_px = canvas_size(settings, barcode)
    except ConfigError:
        width_px, height_px = min(image.width, settings.max_width_px), image.height
        if image.width > settings.max_width_px:
            width_px = settings.max_width_px
            height_px = max(1, int(round(image.height * settings.max_width_px / image.width)))
    return prepare_bitmap(
        image,
        max_width_px=settings.max_width_px,
        width_px=width_px,
        height_px=height_px,
    )


def query_status(settings: Settings) -> dict[str, Any]:
    printer = open_printer(settings)
    try:
        printer.cancel()
        printer.handshake()
        return printer.status()
    finally:
        printer.close()


def print_images(
    settings: Settings,
    images: list[Image.Image],
    *,
    copies: int = 1,
) -> int:
    printer = open_printer(settings)
    try:
        printer.cancel()
        printer.handshake()
        barcode = None
        rfid = printer.get_rfid()
        if isinstance(rfid, dict):
            barcode = rfid.get("barcode") if isinstance(rfid.get("barcode"), str) else None
        for image in images:
            chip = barcode if isinstance(barcode, str) else None
            prepared = prepare_for_print(image, settings, chip)
            printer.print_image(
                prepared,
                density=settings.density,
                copies=copies,
                label_type=settings.label_type,
            )
        return len(images)
    finally:
        printer.close()


def print_paths(settings: Settings, paths: list[Path], *, copies: int = 1) -> int:
    images = [Image.open(path) for path in paths]
    return print_images(settings, images, copies=copies)


def render_to_image(
    settings: Settings,
    *,
    title: str | None = None,
    body: str | None = None,
    qr: str | None = None,
    barcode: str | None = None,
) -> Image.Image:
    width_px, height_px = canvas_size(settings, barcode)
    return render_label(width_px=width_px, height_px=height_px, title=title, body=body, qr=qr)


def render_to_path(
    settings: Settings,
    dest: Path,
    *,
    title: str | None = None,
    body: str | None = None,
    qr: str | None = None,
    barcode: str | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = render_to_image(settings, title=title, body=body, qr=qr, barcode=barcode)
    img.save(dest, format="PNG")
    return dest
