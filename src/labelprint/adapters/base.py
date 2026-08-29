from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from PIL import Image

from labelprint.transport.base import Transport


class PrinterAdapter(ABC):
    name: str

    def __init__(self, transport: Transport):
        self.transport = transport

    @abstractmethod
    def handshake(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def print_image(self, image: Image.Image, *, density: int, copies: int = 1) -> None:
        raise NotImplementedError

    def close(self) -> None:
        closer = getattr(self.transport, "close", None)
        if closer is not None:
            closer()
