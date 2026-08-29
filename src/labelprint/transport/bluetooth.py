from __future__ import annotations

import socket
import sys

from labelprint.errors import TransportError
from labelprint.transport.base import BaseTransport


def normalize_address(address: str) -> str:
    cleaned = address.strip().replace("-", ":").upper()
    parts = cleaned.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        raise TransportError(f"Bluetooth address must look like AA:BB:CC:DD:EE:FF, got {address!r}")
    return ":".join(parts)


def hyphen_address(address: str) -> str:
    return normalize_address(address).replace(":", "-")


class BluetoothTransport(BaseTransport):
    """RFCOMM channel 1 via AF_BLUETOOTH. Works on Linux; not available on macOS CPython."""

    def __init__(self, address: str, channel: int = 1):
        if not hasattr(socket, "AF_BLUETOOTH"):
            raise TransportError(
                "this Python build has no AF_BLUETOOTH; on macOS use transport=rfcomm"
            )
        addr = normalize_address(address)
        try:
            self._sock = socket.socket(
                socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
            )
            self._sock.settimeout(2.0)
            self._sock.connect((addr, channel))
        except OSError as exc:
            raise TransportError(f"Bluetooth RFCOMM connect failed for {addr}: {exc}") from exc

    def read(self, length: int) -> bytes:
        try:
            return self._sock.recv(length)
        except TimeoutError:
            return b""
        except OSError as exc:
            raise TransportError(f"Bluetooth read failed: {exc}") from exc

    def write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def bluetooth_available() -> bool:
    return hasattr(socket, "AF_BLUETOOTH") and sys.platform != "darwin"
