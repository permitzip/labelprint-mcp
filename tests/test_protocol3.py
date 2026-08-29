from __future__ import annotations

from PIL import Image

from labelprint.adapters.protocol3 import (
    GET_INFO,
    PRINT_STATUS,
    Protocol3Printer,
    encode_page_size,
    encode_print_start,
    encode_row_packet,
    parse_heartbeat,
    parse_rfid,
)
from labelprint.packet import FramedPacket


def test_print_start_is_seven_bytes() -> None:
    data = encode_print_start(1)
    assert data == b"\x00\x01\x00\x00\x00\x00\x00"


def test_page_size_is_rows_cols_copies() -> None:
    assert encode_page_size(240, 384, 1) == b"\x00\xf0\x01\x80\x00\x01"


def test_blank_row_uses_0x84() -> None:
    pkt = encode_row_packet(3, 2, b"\x00", printhead_width=384)
    assert pkt.type == 0x84
    assert pkt.data == b"\x00\x03\x02"


def test_ink_row_uses_0x85_and_does_not_widen_counts() -> None:
    line = b"\x80"
    pkt = encode_row_packet(0, 1, line, printhead_width=384)
    assert pkt.type == 0x85
    # >H3BB = y u16 + 3 count bytes + run. Then the bitmap. 6-byte header, not 7.
    assert pkt.data[:6] == b"\x00\x00\x01\x00\x00\x01"
    assert pkt.data[6:] == line


def test_parse_rfid_local_chip() -> None:
    barcode = b"10262260"
    serial = b"PZ1G108305006996"
    raw = (
        bytes.fromhex("881d2a36f3960000")
        + bytes((len(barcode),))
        + barcode
        + bytes((len(serial),))
        + serial
        + b"\x01\x14\x00\x03\x01"
    )
    parsed = parse_rfid(raw)
    assert parsed is not None
    assert parsed["barcode"] == "10262260"
    assert parsed["serial"] == "PZ1G108305006996"
    assert parsed["total"] == 276
    assert parsed["used"] == 3


def test_parse_heartbeat_13_byte() -> None:
    data = bytes(13)
    data = bytearray(data)
    data[10] = 4
    parsed = parse_heartbeat(bytes(data))
    assert parsed["powerlevel"] == 4


class FakeAckTransport:
    def __init__(self) -> None:
        self.written: list[FramedPacket] = []
        self._inbox = bytearray()

    def write(self, data: bytes) -> None:
        pkt = FramedPacket.from_bytes(data)
        self.written.append(pkt)
        expect = _ack_type(pkt)
        if expect is None:
            return
        payload = b"\x00\x01\x00" if pkt.type == PRINT_STATUS else b"\x01"
        self._inbox.extend(FramedPacket(expect, payload).to_bytes())

    def read(self, length: int) -> bytes:
        out = bytes(self._inbox[:length])
        del self._inbox[:length]
        return out

    def close(self) -> None:
        return None


def _ack_type(pkt: FramedPacket) -> int | None:
    if pkt.type in (0x84, 0x85):
        return None
    if pkt.type == GET_INFO:
        return GET_INFO + pkt.data[0]
    table = {
        0xDA: 0xD0,
        0xA5: 0xB5,
        0xDC: 0xD9 if pkt.data == b"\x04" else 0xDD,
        0x54: 0x64,
        0x21: 0x31,
        0x23: 0x33,
        0x01: 0x02,
        0x03: 0x04,
        0x13: 0x14,
        0xE3: 0xE4,
        0xA3: 0xB3,
        0xF3: 0xF4,
        0x1A: 0x1B,
    }
    return table.get(pkt.type, pkt.type + 1)


def test_print_image_sends_protocol3_task() -> None:
    transport = FakeAckTransport()
    printer = Protocol3Printer(transport, printhead_width=384)
    img = Image.new("L", (16, 8), 255)
    img.putpixel((0, 0), 0)
    printer.print_image(img, density=4, copies=1)
    types = [pkt.type for pkt in transport.written]
    assert types[0] == 0x54
    assert 0x01 in types
    assert 0x13 in types
    assert 0x85 in types
    assert types[-2:] == [0xA3, 0xF3]
    start = next(pkt for pkt in transport.written if pkt.type == 0x01)
    assert start.data == encode_print_start(1)
    size = next(pkt for pkt in transport.written if pkt.type == 0x13)
    assert size.data == encode_page_size(8, 16, 1)
