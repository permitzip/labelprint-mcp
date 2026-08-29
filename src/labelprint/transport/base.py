from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol


class Transport(Protocol):
    def read(self, length: int) -> bytes: ...
    def write(self, data: bytes) -> None: ...
    def close(self) -> None: ...


class BaseTransport(ABC):
    @abstractmethod
    def read(self, length: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None
