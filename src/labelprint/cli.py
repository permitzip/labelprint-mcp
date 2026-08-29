from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from labelprint import __version__
from labelprint.config import load_settings
from labelprint.errors import LabelprintError
from labelprint.printer import print_paths, query_status, render_to_path
from labelprint.session import doctor
from labelprint.transport.serial import list_serial_ports


def _settings(args: argparse.Namespace):
    overrides = {
        "transport": getattr(args, "transport", None),
        "address": getattr(args, "address", None),
        "serial_port": getattr(args, "serial_port", None),
        "density": getattr(args, "density", None),
        "width_mm": getattr(args, "width_mm", None),
        "height_mm": getattr(args, "height_mm", None),
        "dpi": getattr(args, "dpi", None),
    }
    return load_settings(config_path=getattr(args, "config", None), overrides=overrides)


def _add_printer_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="TOML config path")
    parser.add_argument("--transport", choices=("auto", "rfcomm", "serial", "bluetooth"))
    parser.add_argument("--address", help="Bluetooth address AA:BB:CC:DD:EE:FF")
    parser.add_argument("--serial-port", dest="serial_port")
    parser.add_argument("--density", type=int)
    parser.add_argument("--width-mm", dest="width_mm", type=float)
    parser.add_argument("--height-mm", dest="height_mm", type=float)
    parser.add_argument("--dpi", type=int)


def cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps(query_status(_settings(args)), indent=2, default=str))
    return 0


def cmd_ports(args: argparse.Namespace) -> int:
    print(json.dumps(list_serial_ports(), indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor(_settings(args))
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 2


def cmd_render(args: argparse.Namespace) -> int:
    if not args.title and not args.body and not args.qr:
        print("render needs --title, --body, and/or --qr", file=sys.stderr)
        return 2
    dest = args.out or Path("label.png")
    path = render_to_path(
        _settings(args),
        dest,
        title=args.title,
        body=args.body,
        qr=args.qr,
    )
    print(str(path.resolve()))
    return 0


def cmd_print(args: argparse.Namespace) -> int:
    if not args.yes:
        print("Refusing to print without --yes (this consumes labels).", file=sys.stderr)
        return 2
    images: list[Path] = []
    if args.image:
        images.extend(args.image)
    if args.title or args.body or args.qr:
        rendered = args.out or Path(".labelprint-render.png")
        render_to_path(
            _settings(args),
            rendered,
            title=args.title,
            body=args.body,
            qr=args.qr,
        )
        images.append(rendered)
    if not images:
        print("print needs --image and/or --title/--body/--qr", file=sys.stderr)
        return 2
    count = print_paths(_settings(args), images, copies=args.copies)
    print(f"printed {count} image(s)")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from labelprint.mcp_server import main as mcp_main

    return mcp_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="labelprint",
        description=(
            "Print PNG labels to a local thermal label printer. Does not call vendor clouds."
        ),
    )
    parser.add_argument("--version", action="version", version=f"labelprint {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    status = sub.add_parser("status", help="Query the printer over the local transport")
    _add_printer_flags(status)
    status.set_defaults(func=cmd_status)

    ports = sub.add_parser("ports", help="List local serial ports")
    ports.set_defaults(func=cmd_ports)

    doc = sub.add_parser("doctor", help="Check config and available transports")
    _add_printer_flags(doc)
    doc.set_defaults(func=cmd_doctor)

    render = sub.add_parser("render", help="Write a preview PNG without printing")
    _add_printer_flags(render)
    render.add_argument("--title")
    render.add_argument("--body")
    render.add_argument("--qr")
    render.add_argument("--out", type=Path, default=Path("label.png"))
    render.set_defaults(func=cmd_render)

    prn = sub.add_parser("print", help="Print a PNG or a rendered title/body/QR label")
    _add_printer_flags(prn)
    prn.add_argument("--image", action="append", type=Path)
    prn.add_argument("--title")
    prn.add_argument("--body")
    prn.add_argument("--qr")
    prn.add_argument("--out", type=Path, help="Where to write a rendered PNG before print")
    prn.add_argument("--copies", type=int, default=1)
    prn.add_argument("--yes", action="store_true", help="Required. Consumes labels.")
    prn.set_defaults(func=cmd_print)

    mcp = sub.add_parser("mcp", help="Run the stdio MCP server")
    mcp.set_defaults(func=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LabelprintError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
