from __future__ import annotations

import serial
from serial.tools.list_ports import comports

from labelprint.errors import TransportError
from labelprint.transport.base import BaseTransport


class SerialTransport(BaseTransport):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.5):
        try:
            self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        except serial.SerialException as exc:
            raise TransportError(f"could not open serial port {port}: {exc}") from exc

    def read(self, length: int) -> bytes:
        return self._serial.read(length)

    def write(self, data: bytes) -> None:
        self._serial.write(data)
        self._serial.flush()

    def close(self) -> None:
        self._serial.close()


def list_serial_ports() -> list[dict[str, str]]:
    return [
        {"port": port, "description": desc, "hwid": hwid} for port, desc, hwid in comports()
    ]
