"""stdio MCP server. Must run on the machine that can see the printer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from PIL import Image

from labelprint.config import load_settings
from labelprint.errors import LabelprintError
from labelprint.printer import print_paths, query_status, render_to_path
from labelprint.session import doctor
from labelprint.transport.serial import list_serial_ports

mcp = FastMCP("labelprint_mcp")


def _settings_from_tool(
    transport: str | None = None,
    address: str | None = None,
    serial_port: str | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
    density: int | None = None,
):
    return load_settings(
        overrides={
            "transport": transport,
            "address": address,
            "serial_port": serial_port,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "density": density,
        }
    )


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)


def _err(exc: Exception) -> str:
    return json.dumps({"ok": False, "error": str(exc), "type": type(exc).__name__})


@mcp.tool()
def labelprint_doctor() -> str:
    """Check local config, serial ports, and which transport this machine would use.

    Does not open the printer. Use this first when setup is unclear.
    """
    try:
        return _ok(doctor(load_settings()))
    except LabelprintError as exc:
        return _err(exc)


@mcp.tool()
def labelprint_list_ports() -> str:
    """List serial device nodes visible on this machine."""
    return _ok({"ports": list_serial_ports()})


@mcp.tool()
def labelprint_status() -> str:
    """Open the configured local printer and return identity, power, and on-device media chip data.

    Media size is not fetched from the internet. If a barcode is present, match it
    against the local config table or pass width_mm/height_mm when printing.
    """
    try:
        return _ok({"ok": True, "status": query_status(load_settings())})
    except LabelprintError as exc:
        return _err(exc)


@mcp.tool()
def labelprint_render(
    title: str | None = None,
    body: str | None = None,
    qr: str | None = None,
    out_path: str | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
) -> str:
    """Render a preview PNG (title, body, and/or QR). Does not print."""
    if not title and not body and not qr:
        return _err(ValueError("render needs title, body, and/or qr"))
    dest = Path(out_path) if out_path else Path.cwd() / "labelprint-preview.png"
    try:
        settings = _settings_from_tool(width_mm=width_mm, height_mm=height_mm)
        path = render_to_path(settings, dest, title=title, body=body, qr=qr)
        image = Image.open(path)
        return _ok(
            {
                "ok": True,
                "path": str(path.resolve()),
                "width_px": image.width,
                "height_px": image.height,
            }
        )
    except (LabelprintError, OSError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def labelprint_print(
    confirm: bool = False,
    image_path: str | None = None,
    title: str | None = None,
    body: str | None = None,
    qr: str | None = None,
    copies: int = 1,
    width_mm: float | None = None,
    height_mm: float | None = None,
    density: int | None = None,
) -> str:
    """Print a PNG, or render title/body/QR and print that.

    Consumes physical labels. confirm must be true. Preview with labelprint_render first.
    """
    if not confirm:
        return _err(
            PermissionError(
                "confirm=false; call labelprint_render first, then reprint with confirm=true"
            )
        )
    if copies < 1:
        return _err(ValueError("copies must be >= 1"))
    settings = _settings_from_tool(width_mm=width_mm, height_mm=height_mm, density=density)
    paths: list[Path] = []
    try:
        if title or body or qr:
            rendered = Path.cwd() / "labelprint-job.png"
            paths.append(render_to_path(settings, rendered, title=title, body=body, qr=qr))
        if image_path:
            path = Path(image_path)
            if not path.is_file():
                return _err(FileNotFoundError(f"image not found: {image_path}"))
            paths.append(path)
        if not paths:
            return _err(ValueError("pass image_path and/or title/body/qr"))
        count = print_paths(settings, paths, copies=copies)
        return _ok(
            {"ok": True, "printed": count, "copies": copies, "paths": [str(p) for p in paths]}
        )
    except (LabelprintError, OSError, ValueError) as exc:
        return _err(exc)


def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
