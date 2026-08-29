from __future__ import annotations

import sys
from typing import Any

from labelprint.adapters.protocol3 import Protocol3Printer
from labelprint.config import Settings
from labelprint.errors import ConfigError, TransportError
from labelprint.transport.bluetooth import BluetoothTransport, bluetooth_available
from labelprint.transport.rfcomm_bridge import RFCOMMBridgeTransport
from labelprint.transport.serial import SerialTransport, list_serial_ports


def open_transport(settings: Settings):
    kind = settings.transport
    if kind == "auto":
        kind = _auto_transport(settings)
    if kind == "rfcomm":
        if not settings.address:
            raise ConfigError("transport=rfcomm needs LABELPRINT_ADDRESS or printer.address")
        return RFCOMMBridgeTransport(settings.address)
    if kind == "bluetooth":
        if not settings.address:
            raise ConfigError("transport=bluetooth needs LABELPRINT_ADDRESS or printer.address")
        return BluetoothTransport(settings.address)
    if kind == "serial":
        port = settings.serial_port
        if not port:
            raise ConfigError(
                "transport=serial needs LABELPRINT_SERIAL_PORT or printer.serial_port"
            )
        return SerialTransport(port)
    raise ConfigError(f"unknown transport {kind!r}")


def _auto_transport(settings: Settings) -> str:
    if sys.platform == "darwin":
        if settings.address:
            return "rfcomm"
        if settings.serial_port:
            return "serial"
        raise ConfigError(
            "set printer.address (Bluetooth) or printer.serial_port; macOS usually needs RFCOMM"
        )
    if settings.address and bluetooth_available():
        return "bluetooth"
    if settings.serial_port:
        return "serial"
    raise ConfigError("set printer.address or printer.serial_port")


def open_printer(settings: Settings) -> Protocol3Printer:
    if settings.adapter != "protocol3":
        raise ConfigError(f"unsupported adapter {settings.adapter!r}")
    transport = open_transport(settings)
    return Protocol3Printer(transport, printhead_width=settings.max_width_px)


def doctor(settings: Settings) -> dict[str, Any]:
    report: dict[str, Any] = {
        "platform": sys.platform,
        "transport": settings.transport,
        "resolved_transport": None,
        "address": settings.address,
        "serial_port": settings.serial_port,
        "config_path": str(settings.config_path) if settings.config_path else None,
        "serial_ports": list_serial_ports(),
        "bluetooth_socket": bluetooth_available(),
        "ok": False,
        "notes": [],
    }
    try:
        report["resolved_transport"] = (
            settings.transport if settings.transport != "auto" else _auto_transport(settings)
        )
    except (ConfigError, TransportError) as exc:
        report["notes"].append(str(exc))
        return report
    if report["resolved_transport"] == "rfcomm":
        from labelprint.transport.rfcomm_bridge import package_swift_source

        src = package_swift_source()
        report["bridge_source"] = str(src)
        report["bridge_source_present"] = src.is_file()
        if sys.platform != "darwin":
            report["notes"].append("RFCOMM bridge is macOS-only")
    report["ok"] = not report["notes"]
    if report["ok"]:
        report["notes"].append(
            "config looks printable; run `labelprint status` with the printer on"
        )
    return report
