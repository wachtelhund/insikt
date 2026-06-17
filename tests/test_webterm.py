"""Unit tests for the stdlib WebSocket codec used by the web terminal."""
from __future__ import annotations

import struct

from insikt import webterm


def test_accept_rfc_vector():
    # RFC 6455 example key/accept pair.
    assert webterm._accept("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def _client_frame(payload: bytes, opcode=0x2, mask=b"\x01\x02\x03\x04") -> bytes:
    n = len(payload)
    hdr = bytes([0x80 | opcode])
    if n < 126:
        hdr += bytes([0x80 | n])
    elif n < 65536:
        hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return hdr + mask + masked


def test_take_frame_unmasks_payload():
    buf = bytearray(_client_frame(b"hello world", opcode=0x2))
    op, data = webterm._take_frame(buf)
    assert op == 0x2 and data == b"hello world" and len(buf) == 0


def test_take_frame_incomplete_returns_none():
    full = _client_frame(b"x" * 300)  # uses 16-bit length
    assert webterm._take_frame(bytearray(full[:5])) is None  # header not all there
    op, data = webterm._take_frame(bytearray(full))
    assert op == 0x2 and data == b"x" * 300


def test_take_frame_consumes_only_one():
    buf = bytearray(_client_frame(b"aaa") + _client_frame(b"bbb"))
    op1, d1 = webterm._take_frame(buf)
    op2, d2 = webterm._take_frame(buf)
    assert d1 == b"aaa" and d2 == b"bbb" and len(buf) == 0


class _FakeSock:
    def __init__(self):
        self.sent = bytearray()
    def sendall(self, b):
        self.sent.extend(b)


def test_send_frame_header_unmasked():
    s = _FakeSock()
    webterm._send(s, b"hi", 0x2)
    assert s.sent[0] == 0x80 | 0x2  # FIN + binary
    assert s.sent[1] == 2 and bytes(s.sent[2:]) == b"hi"  # server frames not masked


def test_send_16bit_length():
    s = _FakeSock()
    webterm._send(s, b"y" * 200, 0x1)
    assert s.sent[1] == 126 and struct.unpack(">H", bytes(s.sent[2:4]))[0] == 200
