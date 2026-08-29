from pathlib import Path

from labelprint.config import load_settings, media_for_barcode


def test_toml_media_and_barcode_table(tmp_path: Path) -> None:
    path = tmp_path / "labelprint.toml"
    path.write_text(
        """
[printer]
transport = "serial"
serial_port = "/dev/cu.fake"
density = 3

[media]
width_mm = 40
height_mm = 20
dpi = 203

[[media.barcode]]
code = "10262260"
width_mm = 50
height_mm = 30
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path=path)
    assert settings.transport == "serial"
    assert settings.serial_port == "/dev/cu.fake"
    assert settings.density == 3
    assert media_for_barcode(settings, None)[:2] == (40, 20)
    assert media_for_barcode(settings, "10262260")[:2] == (50, 30)


def test_overrides_win(tmp_path: Path) -> None:
    path = tmp_path / "labelprint.toml"
    path.write_text("[printer]\ntransport = 'serial'\nserial_port = '/dev/a'\n", encoding="utf-8")
    settings = load_settings(config_path=path, overrides={"serial_port": "/dev/b"})
    assert settings.serial_port == "/dev/b"
