# labelprint

Local MCP server and CLI that print PNG labels to a nearby thermal label printer.

It runs on the machine that can see the printer. It does not call manufacturer cloud APIs, does not scrape template catalogs, and is not named after any printer brand.

```text
PNG or title/body/QR  →  1-bit bitmap  →  local serial / RFCOMM  →  paper
```

## Install

```bash
pip install git+https://github.com/permitzip/labelprint-mcp
```

Optional QR rendering:

```bash
pip install "labelprint[qr] @ git+https://github.com/permitzip/labelprint-mcp"
```

On macOS, Bluetooth printing needs [Xcode Command Line Tools](https://developer.apple.com/xcode/resources/) so the small IOBluetooth helper can compile on first use (`swiftc`).

## Configure

Copy [`examples/config.toml`](examples/config.toml) to `~/.config/labelprint/config.toml` (or `./labelprint.toml`).

```toml
[printer]
transport = "auto"
address = "AA:BB:CC:DD:EE:FF"
density = 4
max_width_px = 384

[media]
width_mm = 50
height_mm = 30
dpi = 203
```

Environment variables use the `LABELPRINT_` prefix (`LABELPRINT_ADDRESS`, `LABELPRINT_WIDTH_MM`, …).

**Roll size is local.** The printer can report a chip barcode; this tool will not look that code up on the internet. Put `width_mm` / `height_mm` in config, pass `--width-mm` / `--height-mm`, or add a `[[media.barcode]]` row that you measured yourself.

## CLI

```bash
labelprint doctor
labelprint ports
labelprint status
labelprint render --title "BOARDS" --body "Is this a controller?" --out preview.png
labelprint print --image preview.png --yes
labelprint print --title "ITEM" --qr "https://example.com/i/123" --yes
labelprint mcp
```

`print` refuses to run without `--yes`. That flag consumes labels.

## MCP

The server is stdio-only. Point Cursor or Claude Desktop at the machine with the printer:

```json
{
  "mcpServers": {
    "labelprint": {
      "command": "labelprint-mcp"
    }
  }
}
```

A full example is in [`examples/mcp.json`](examples/mcp.json).

| Tool | What it does |
| --- | --- |
| `labelprint_doctor` | Config and transport check (no print) |
| `labelprint_list_ports` | Serial nodes on this machine |
| `labelprint_status` | Identity, power, on-device chip fields |
| `labelprint_render` | Preview PNG |
| `labelprint_print` | Print. Requires `confirm: true`. |

A hosted agent (ChatGPT, a cloud Hours worker, Docker on a laptop) cannot open this printer. Run this MCP locally, or later on a Pi that sits next to the printer.

## Transports

| Name | When |
| --- | --- |
| `rfcomm` | macOS Bluetooth via IOBluetooth RFCOMM channel 1 |
| `bluetooth` | Linux `AF_BLUETOOTH` RFCOMM |
| `serial` | USB or a working `/dev/cu.*` / `COM` port |
| `auto` | macOS + address → `rfcomm`; Linux + address → `bluetooth`; otherwise serial |

On some Macs the Bluetooth serial node opens and then never exchanges protocol bytes after reconnect. Prefer `rfcomm` there.

## Compatible hardware

The first adapter is **protocol3**: 203 dpi, ~384 px printhead, firmware that needs a 7-byte print-start and a 6-byte page-size. That matches several common Bluetooth label printers (device type `4096` is one of them).

This is an unofficial local driver. It is not affiliated with, endorsed by, or supported by any printer manufacturer. Packet framing is derived from [niimprint](https://github.com/AndBondStyle/niimprint) (MIT). The print task was completed from device traces and community protocol notes. See `NOTICE`.

## Library

```python
from pathlib import Path
from labelprint.config import load_settings
from labelprint.printer import print_paths, render_to_path

settings = load_settings()
render_to_path(settings, Path("preview.png"), title="BOARDS", body="Controller?")
print_paths(settings, [Path("preview.png")])
```

## License

MIT. See `LICENSE` and `NOTICE`.
