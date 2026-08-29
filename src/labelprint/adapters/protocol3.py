"""Protocol-3 print task for 203 dpi Bluetooth/serial label printers.

Stock 1-byte PrintStart is ACKed by firmware 13.x and never feeds paper.
This adapter does the handshake, 7-byte PrintStart, 6-byte page size,
paced bitmap rows, and print-status poll.

Dark pixels are ink (bit 1). Do not invert the bitmap.
"""

from __future__ import annotations

import struct
import time
from enum import IntEnum
from typing import Any

from PIL import Image

from labelprint.errors import PrinterError
from labelprint.imageutil import encode_rows, split_ink_counts
from labelprint.packet import FramedPacket, PacketError
from labelprint.transport.base import Transport

NACK = 0xDB
GET_INFO = 0x40
GET_RFID = 0x1A
HEARTBEAT = 0xDC
SET_DENSITY = 0x21
SET_LABEL_TYPE = 0x23
PRINT_START = 0x01
PAGE_START = 0x03
SET_PAGE_SIZE = 0x13
ROW_BLANK = 0x84
ROW_INK = 0x85
PAGE_END = 0xE3
PRINT_STATUS = 0xA3
PRINT_END = 0xF3
CANCEL = 0xDA
RFID_WAKE = 0x54
PRINTER_STATUS = 0xA5


class InfoKey(IntEnum):
    DENSITY = 1
    PRINTSPEED = 2
    LABELTYPE = 3
    LANGUAGETYPE = 6
    AUTOSHUTDOWNTIME = 7
    DEVICETYPE = 8
    SOFTVERSION = 9
    BATTERY = 10
    DEVICESERIAL = 11
    HARDVERSION = 12


def decode_info(key: InfoKey, data: bytes) -> int | float | str | None:
    if not data:
        return None
    if key is InfoKey.DEVICESERIAL:
        text = data.decode("ascii", errors="ignore").strip("\x00")
        if text.isprintable() and text:
            return text
        return data.hex()
    value = int.from_bytes(data, "big")
    if key in (InfoKey.SOFTVERSION, InfoKey.HARDVERSION):
        return value / 100
    return value


def parse_rfid(data: bytes) -> dict[str, Any] | None:
    if not data or data[0] == 0:
        return None
    if len(data) < 9:
        return {"raw_hex": data.hex()}
    uuid = data[0:8].hex()
    idx = 8
    barcode_len = data[idx]
    idx += 1
    barcode = data[idx : idx + barcode_len].decode("ascii", errors="replace")
    idx += barcode_len
    if idx >= len(data):
        return {"uuid": uuid, "barcode": barcode, "raw_hex": data.hex()}
    serial_len = data[idx]
    idx += 1
    serial = data[idx : idx + serial_len].decode("ascii", errors="replace")
    idx += serial_len
    parsed: dict[str, Any] = {
        "uuid": uuid,
        "barcode": barcode,
        "serial": serial,
    }
    if len(data) - idx >= 5:
        total_len, used_len, type_ = struct.unpack(">HHB", data[idx : idx + 5])
        parsed.update({"total": total_len, "used": used_len, "label_type": type_})
    return parsed


def parse_heartbeat(data: bytes) -> dict[str, Any]:
    closingstate = powerlevel = paperstate = rfidreadstate = None
    match len(data):
        case 20:
            paperstate = data[18]
            rfidreadstate = data[19]
        case 13:
            closingstate = data[9]
            powerlevel = data[10]
            paperstate = data[11]
            rfidreadstate = data[12]
        case 19:
            closingstate = data[15]
            powerlevel = data[16]
            paperstate = data[17]
            rfidreadstate = data[18]
        case 10:
            closingstate = data[8]
            powerlevel = data[9]
            rfidreadstate = data[8]
        case 9:
            closingstate = data[8]
    return {
        "closingstate": closingstate,
        "powerlevel": powerlevel,
        "paperstate": paperstate,
        "rfidreadstate": rfidreadstate,
        "raw_hex": data.hex(),
    }


def encode_print_start(page_count: int = 1) -> bytes:
    return struct.pack(">H5B", page_count, 0, 0, 0, 0, 0)


def encode_page_size(rows: int, cols: int, copies: int = 1) -> bytes:
    return struct.pack(">HHH", rows, cols, copies)


def encode_row_packet(
    y: int,
    run: int,
    line: bytes,
    *,
    printhead_width: int,
) -> FramedPacket:
    if sum(b.bit_count() for b in line) == 0:
        return FramedPacket(ROW_BLANK, struct.pack(">HB", y, run))
    c0, c1, c2 = split_ink_counts(line, printhead_width)
    header = struct.pack(">H3BB", y, c0, c1, c2, run)
    return FramedPacket(ROW_INK, header + line)


class Protocol3Printer:
    name = "protocol3"

    def __init__(self, transport: Transport, *, printhead_width: int = 384):
        self.transport = transport
        self.printhead_width = printhead_width
        self._buf = bytearray()

    def _send(self, packet: FramedPacket) -> None:
        self.transport.write(packet.to_bytes())

    def _recv(self, timeout: float = 0.8) -> list[FramedPacket]:
        deadline = time.time() + timeout
        packets: list[FramedPacket] = []
        while time.time() < deadline:
            chunk = self.transport.read(1024)
            if chunk:
                self._buf.extend(chunk)
                while len(self._buf) > 4:
                    pkt_len = self._buf[3] + 7
                    if len(self._buf) < pkt_len:
                        break
                    raw = bytes(self._buf[:pkt_len])
                    del self._buf[:pkt_len]
                    try:
                        packets.append(FramedPacket.from_bytes(raw))
                    except PacketError:
                        continue
                if packets:
                    return packets
            else:
                time.sleep(0.02)
        return packets

    def transceive(
        self,
        req: int,
        data: bytes,
        expect: int | None = None,
        timeout: float = 1.2,
    ) -> FramedPacket | None:
        if expect is None:
            expect = req + 1
        self._send(FramedPacket(req, data))
        deadline = time.time() + timeout
        while time.time() < deadline:
            for pkt in self._recv(0.15):
                if pkt.type == NACK:
                    raise PrinterError(f"printer nack for 0x{req:02x}")
                if pkt.type == expect:
                    return pkt
                if req == GET_INFO and data and pkt.type == GET_INFO + data[0]:
                    return pkt
            time.sleep(0.03)
        return None

    def cancel(self) -> None:
        self.transceive(CANCEL, b"\x01", 0xD0)

    def handshake(self) -> None:
        self.transceive(PRINTER_STATUS, b"\x01", 0xB5)
        for sub in (0x08, 0x0B, 0x0D, 0x0A, 0x07, 0x03, 0x0C, 0x09):
            self.transceive(GET_INFO, bytes((sub,)), GET_INFO + sub)
        hb = self.transceive(HEARTBEAT, b"\x04", 0xD9)
        if hb is None:
            self.transceive(HEARTBEAT, b"\x01", 0xDD)

    def get_info(self, key: InfoKey) -> int | float | str | None:
        pkt = self.transceive(GET_INFO, bytes((int(key),)), GET_INFO + int(key))
        if pkt is None:
            return None
        return decode_info(key, pkt.data)

    def get_rfid(self) -> dict[str, Any] | None:
        pkt = self.transceive(GET_RFID, b"\x01")
        if pkt is None:
            return None
        return parse_rfid(pkt.data)

    def heartbeat(self) -> dict[str, Any] | None:
        pkt = self.transceive(HEARTBEAT, b"\x01")
        if pkt is None:
            return None
        return parse_heartbeat(pkt.data)

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {}
        for key in InfoKey:
            info[key.name.lower()] = self.get_info(key)
        return {
            "adapter": self.name,
            "info": info,
            "heartbeat": self.heartbeat(),
            "rfid": self.get_rfid(),
        }

    def print_image(
        self,
        image: Image.Image,
        *,
        density: int,
        copies: int = 1,
        label_type: int = 1,
    ) -> None:
        if image.width > self.printhead_width:
            raise PrinterError(f"width {image.width} > printhead {self.printhead_width}")
        if copies < 1:
            raise PrinterError("copies must be >= 1")
        gray = image.convert("L")
        rows, cols = gray.height, gray.width

        self.transceive(RFID_WAKE, b"\x01", 0x64)
        self.transceive(SET_DENSITY, bytes((density,)), 0x31)
        self.transceive(SET_LABEL_TYPE, bytes((label_type,)), 0x33)

        start = self.transceive(PRINT_START, encode_print_start(1), 0x02)
        if start is None:
            raise PrinterError("PrintStart was not acknowledged")
        self.transceive(PAGE_START, b"\x01", 0x04)
        size = self.transceive(SET_PAGE_SIZE, encode_page_size(rows, cols, copies), 0x14)
        if size is None:
            raise PrinterError("SetPageSize was not acknowledged")

        for y, run, line in encode_rows(gray):
            self._send(encode_row_packet(y, run, line, printhead_width=self.printhead_width))
            time.sleep(0.015)

        self.transceive(PAGE_END, b"\x01", 0xE4)
        page_done = False
        for _ in range(80):
            st = self.transceive(PRINT_STATUS, b"\x01", 0xB3)
            if st and len(st.data) >= 2:
                page_n = int.from_bytes(st.data[0:2], "big")
                if page_n >= 1:
                    page_done = True
                    break
            time.sleep(0.25)
        if not page_done:
            raise PrinterError("printer never reported page>=1 — paper likely did not move")
        self.transceive(PRINT_END, b"\x01", 0xF4)

    def close(self) -> None:
        closer = getattr(self.transport, "close", None)
        if closer is not None:
            closer()
