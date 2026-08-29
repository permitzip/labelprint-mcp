"""Local thermal label printing — CLI, library, and MCP server."""

from labelprint.config import Settings
from labelprint.errors import LabelprintError, PrinterError, TransportError
from labelprint.packet import FramedPacket

__all__ = [
    "FramedPacket",
    "LabelprintError",
    "PrinterError",
    "Settings",
    "TransportError",
    "__version__",
]

__version__ = "0.1.0"
