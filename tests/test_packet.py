from labelprint.packet import FramedPacket, PacketError


def test_roundtrip() -> None:
    pkt = FramedPacket(0x01, b"\x00\x01")
    raw = pkt.to_bytes()
    assert raw[:2] == b"\x55\x55"
    assert raw[-2:] == b"\xaa\xaa"
    assert FramedPacket.from_bytes(raw) == pkt


def test_checksum_detects_corruption() -> None:
    raw = bytearray(FramedPacket(0x21, b"\x04").to_bytes())
    raw[4] ^= 0xFF
    try:
        FramedPacket.from_bytes(bytes(raw))
    except PacketError:
        return
    raise AssertionError("expected PacketError")
