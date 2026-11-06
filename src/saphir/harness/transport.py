"""Transports for the harness: plug SAPHIR into any byte pipe.

The protocol itself is transport-agnostic; a transport only has to move whole
envelopes (already ``u32 length || CBOR``) and preserve order. Three ship here:

- ``LoopbackTransport``: both endpoints in one process (demo, tests).
- ``FileTransport``: a shared directory with one inbox per agent (two local
  processes, no ports, no audio hardware).
- ``TcpTransport``: raw frames over a TCP stream (two machines on a LAN).

The acoustic path lives in ``demo/web`` (ggwave WASM); anything that can hand
you bytes can implement this interface and be used by the harness.
"""
from __future__ import annotations

import os
import queue
import socket
import struct
import time
import uuid
from pathlib import Path

DEFAULT_TIMEOUT = 10.0


class TransportError(Exception):
    pass


class Transport:
    """Whole-envelope, ordered, bidirectional byte pipe."""

    name = "transport"

    def send(self, frame: bytes) -> None:
        raise NotImplementedError

    def recv(self, timeout: float | None = DEFAULT_TIMEOUT) -> bytes | None:
        """Return one frame, or None on timeout."""
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class LoopbackTransport(Transport):
    """Two in-process endpoints connected by thread-safe queues."""

    name = "loopback"

    def __init__(self, inbox: queue.Queue, outbox: queue.Queue):
        self._inbox = inbox
        self._outbox = outbox
        self._closed = False

    @classmethod
    def pair(cls) -> tuple["LoopbackTransport", "LoopbackTransport"]:
        ab: queue.Queue = queue.Queue()
        ba: queue.Queue = queue.Queue()
        return cls(ba, ab), cls(ab, ba)

    def send(self, frame: bytes) -> None:
        if self._closed:
            raise TransportError("loopback transport closed")
        self._outbox.put(bytes(frame))

    def recv(self, timeout: float | None = DEFAULT_TIMEOUT) -> bytes | None:
        try:
            return self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        self._closed = True


class FileTransport(Transport):
    """Shared-directory pipe: atomic writes into the peer's inbox.

    Frames are written to a temp name and renamed, so a reader never sees a
    half-written envelope. ``inbox``/``peer_inbox`` are subdirectory names.
    """

    name = "file"

    def __init__(self, root: str | Path, inbox: str, peer_inbox: str,
                 poll_s: float = 0.02):
        self.root = Path(root)
        self.inbox = self.root / inbox
        self.peer_inbox = self.root / peer_inbox
        self.poll_s = poll_s
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.peer_inbox.mkdir(parents=True, exist_ok=True)
        self._tag = f"{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._n = 0
        self._closed = False

    def send(self, frame: bytes) -> None:
        self._n += 1
        name = f"{time.time_ns():020d}-{self._tag}-{self._n:04d}.frame"
        tmp = self.peer_inbox / f".{name}.tmp"
        final = self.peer_inbox / name
        tmp.write_bytes(bytes(frame))
        os.replace(tmp, final)

    def recv(self, timeout: float | None = DEFAULT_TIMEOUT) -> bytes | None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            frames = sorted(self.inbox.glob("*.frame"))
            if frames:
                p = frames[0]
                try:
                    data = p.read_bytes()
                except FileNotFoundError:  # another reader won the race
                    continue
                p.unlink(missing_ok=True)
                return data
            if deadline is not None and time.monotonic() >= deadline:
                return None
            if deadline is None and self._closed:
                return None
            time.sleep(self.poll_s)

    def close(self) -> None:
        self._closed = True


class TcpTransport(Transport):
    """Frames over a TCP stream, using the protocol's own length prefix."""

    name = "tcp"

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = bytearray()

    @classmethod
    def connect(cls, host: str, port: int, timeout: float = 10.0) -> "TcpTransport":
        return cls(socket.create_connection((host, port), timeout=timeout))

    @classmethod
    def listen(cls, host: str, port: int) -> "TcpTransport":
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(1)
        conn, _ = srv.accept()
        srv.close()
        return cls(conn)

    def send(self, frame: bytes) -> None:
        self.sock.sendall(bytes(frame))

    def _fill(self) -> bool:
        chunk = self.sock.recv(4096)
        if not chunk:
            return False
        self._buf += chunk
        return True

    def recv(self, timeout: float | None = DEFAULT_TIMEOUT) -> bytes | None:
        self.sock.settimeout(timeout)
        try:
            while len(self._buf) < 4:
                if not self._fill():
                    return None
            (n,) = struct.unpack(">I", self._buf[:4])
            while len(self._buf) < 4 + n:
                if not self._fill():
                    return None
            frame = bytes(self._buf[:4 + n])
            del self._buf[:4 + n]
            return frame
        except (socket.timeout, TimeoutError):
            return None

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def parse_hostport(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    if not host or not port.isdigit():
        raise ValueError(f"expected HOST:PORT, got {value!r}")
    return host, int(port)
