"""Settings from environment, optional TOML, and CLI overrides.

Precedence: defaults < environment < config file < explicit overrides.
Never phones a manufacturer cloud. Media size is local config, CLI flags,
or a barcode table you maintain yourself.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from labelprint.errors import ConfigError

TransportName = Literal["auto", "rfcomm", "serial", "bluetooth"]
AdapterName = Literal["protocol3"]


class BarcodeMedia(BaseModel):
    code: str
    width_mm: float
    height_mm: float
    dpi: int = 203


class Settings(BaseModel):
    transport: TransportName = "auto"
    address: str | None = None
    serial_port: str | None = None
    adapter: AdapterName = "protocol3"
    density: int = Field(default=4, ge=1, le=5)
    max_width_px: int = Field(default=384, ge=8, le=832)
    dpi: int = Field(default=203, ge=100, le=600)
    width_mm: float | None = None
    height_mm: float | None = None
    label_type: int = Field(default=1, ge=1, le=3)
    config_path: Path | None = None
    barcodes: list[BarcodeMedia] = Field(default_factory=list)

    @field_validator("address", "serial_port", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LABELPRINT_", extra="ignore")

    transport: TransportName = "auto"
    address: str | None = None
    serial_port: str | None = None
    adapter: AdapterName = "protocol3"
    density: int = 4
    max_width_px: int = 384
    dpi: int = 203
    width_mm: float | None = None
    height_mm: float | None = None
    label_type: int = 1


def default_config_paths() -> list[Path]:
    home = Path.home()
    paths = [
        Path.cwd() / "labelprint.toml",
        home / ".config" / "labelprint" / "config.toml",
    ]
    if sys.platform == "darwin":
        paths.insert(1, home / "Library" / "Application Support" / "labelprint" / "config.toml")
    return paths


def _load_toml(path: Path) -> dict[str, object]:
    data = tomllib.loads(path.read_text())
    printer = data.get("printer", {})
    media = data.get("media", {})
    if not isinstance(printer, dict) or not isinstance(media, dict):
        raise ConfigError(f"{path} must have [printer] and optional [media] tables")
    merged: dict[str, object] = {}
    merged.update(printer)
    if "width_mm" in media:
        merged["width_mm"] = media["width_mm"]
    if "height_mm" in media:
        merged["height_mm"] = media["height_mm"]
    if "dpi" in media:
        merged["dpi"] = media["dpi"]
    barcodes = media.get("barcode", [])
    if isinstance(barcodes, dict):
        barcodes = [barcodes]
    if isinstance(barcodes, list):
        merged["barcodes"] = barcodes
    return merged


def load_settings(
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, object] | None = None,
) -> Settings:
    merged: dict[str, object] = _EnvSettings().model_dump()
    file_values: dict[str, object] = {}
    chosen: Path | None = Path(config_path) if config_path else None
    if chosen is None:
        for candidate in default_config_paths():
            if candidate.is_file():
                chosen = candidate
                break
    if chosen is not None:
        if not chosen.is_file():
            raise ConfigError(f"config file not found: {chosen}")
        file_values = _load_toml(chosen)
        file_values["config_path"] = chosen
    merged.update(file_values)
    if overrides:
        merged.update({key: value for key, value in overrides.items() if value is not None})
    return Settings.model_validate(merged)


def media_for_barcode(
    settings: Settings, barcode: str | None
) -> tuple[float | None, float | None, int]:
    if barcode:
        for row in settings.barcodes:
            if row.code == barcode:
                return row.width_mm, row.height_mm, row.dpi
    return settings.width_mm, settings.height_mm, settings.dpi
