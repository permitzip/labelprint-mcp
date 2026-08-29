class LabelprintError(Exception):
    """Base error for the labelprint library."""


class ConfigError(LabelprintError):
    """Settings are missing or invalid."""


class TransportError(LabelprintError):
    """Could not open or talk to the local transport."""


class PrinterError(LabelprintError):
    """The printer NACKed or never finished a print task."""


class ImageError(LabelprintError):
    """The label image cannot be prepared for this adapter."""
