"""Framed command packets used by protocol-3 thermal label printers.

Derived from niimprint's MIT-licensed packet codec (Copyright 2023 kjy00302).
See NOTICE.
"""

from __future__ import annotations

from dataclasses import dataclass


class PacketError(ValueError):
    """Bytes are not a valid framed packet."""


@dataclass(frozen=True, slots=True)
class FramedPacket:
    type: int
    data: bytes

    @classmethod
    def from_bytes(cls, pkt: bytes) -> FramedPacket:
        if len(pkt) < 7:
            raise PacketError(f"packet too short: {len(pkt)} bytes")
        if pkt[:2] != b"\x55\x55" or pkt[-2:] != b"\xaa\xaa":
            raise PacketError("missing frame markers")
        type_ = pkt[2]
        length = pkt[3]
        expected = length + 7
        if len(pkt) < expected:
            raise PacketError(f"truncated packet: have {len(pkt)}, need {expected}")
        data = pkt[4 : 4 + length]
        checksum = type_ ^ length
        for byte in data:
            checksum ^= byte
        if checksum != pkt[-3]:
            raise PacketError("checksum mismatch")
        return cls(type_, data)

    def to_bytes(self) -> bytes:
        checksum = self.type ^ len(self.data)
        for byte in self.data:
            checksum ^= byte
        return bytes((0x55, 0x55, self.type, len(self.data), *self.data, checksum, 0xAA, 0xAA))

    def __repr__(self) -> str:
        return f"<FramedPacket type=0x{self.type:02x} data={self.data.hex()}>"
