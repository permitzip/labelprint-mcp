"""macOS RFCOMM via a small IOBluetooth helper.

CPython on macOS can open ``/dev/cu.*`` nodes that never exchange protocol
bytes after Bluetooth reconnects. IOBluetooth RFCOMM channel 1 does.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from labelprint.errors import TransportError
from labelprint.transport.base import BaseTransport
from labelprint.transport.bluetooth import hyphen_address

SWIFT_NAME = "rfcomm_bridge.swift"


def package_swift_source() -> Path:
    return Path(__file__).resolve().parent.parent / "native" / "macos" / SWIFT_NAME


def cached_binary_path() -> Path:
    return Path.home() / ".cache" / "labelprint" / "rfcomm_bridge"


def compile_bridge(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_mtime >= source.stat().st_mtime:
        return dest
    if sys.platform != "darwin":
        raise TransportError("the RFCOMM bridge is a macOS IOBluetooth helper")
    cmd = [
        "swiftc",
        "-O",
        "-framework",
        "IOBluetooth",
        "-o",
        str(dest),
        str(source),
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise TransportError(
            "swiftc not found; install Xcode Command Line Tools to build the macOS RFCOMM bridge"
        ) from exc
    if proc.returncode != 0:
        raise TransportError(f"swiftc failed:\n{proc.stderr or proc.stdout}")
    dest.chmod(0o755)
    return dest


def ensure_bridge_binary() -> Path:
    source = package_swift_source()
    if not source.is_file():
        raise TransportError(f"missing RFCOMM bridge source at {source}")
    return compile_bridge(source, cached_binary_path())


class RFCOMMBridgeTransport(BaseTransport):
    def __init__(self, address: str, bridge: Path | None = None):
        binary = bridge or ensure_bridge_binary()
        if not binary.exists():
            raise TransportError(f"missing RFCOMM bridge at {binary}")
        addr = hyphen_address(address)
        self.proc = subprocess.Popen(
            [str(binary), addr],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error: str | None = None
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        if not self._ready.wait(12):
            self.close()
            raise TransportError(self._error or "RFCOMM bridge did not become ready")
        if self._error:
            self.close()
            raise TransportError(self._error)

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if line == "!ready":
                self._ready.set()
            elif line.startswith("!error"):
                self._error = line
                self._ready.set()
            elif line.startswith("<"):
                with self._lock:
                    self._buf.extend(bytes.fromhex(line[1:]))

    def _read_stderr(self) -> None:
        assert self.proc.stderr is not None
        for _line in self.proc.stderr:
            pass

    def read(self, length: int) -> bytes:
        deadline = time.time() + 0.35
        out = bytearray()
        while len(out) < length and time.time() < deadline:
            with self._lock:
                take = min(length - len(out), len(self._buf))
                if take:
                    out.extend(self._buf[:take])
                    del self._buf[:take]
            if len(out) < length:
                time.sleep(0.01)
        return bytes(out)

    def write(self, data: bytes) -> None:
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(">" + data.hex() + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError as exc:
            raise TransportError("RFCOMM bridge stdin closed") from exc

    def close(self) -> None:
        if self.proc.stdin:
            try:
                self.proc.stdin.write("Q\n")
                self.proc.stdin.flush()
            except BrokenPipeError:
                pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
