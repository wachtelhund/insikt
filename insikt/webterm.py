"""A PTY-backed shell over a hand-rolled WebSocket — stdlib only.

Powers the optional web terminal. The browser (xterm.js) opens a WebSocket to
``/ws/term``; this module performs the WebSocket handshake on the existing
``http.server`` socket, spawns an interactive login shell attached to a
pseudo-terminal (stdlib ``pty``), and pumps raw bytes both ways so the browser
gets a real terminal (keyboard shortcuts, ANSI colors, full-screen apps).

Unix-only (``pty``). Gated by ``server.terminal.enabled`` — this is interactive
remote shell access to the host by design.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import select
import struct

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def is_ws(handler) -> bool:
    return (handler.headers.get("Upgrade", "").lower() == "websocket"
            and bool(handler.headers.get("Sec-WebSocket-Key")))


def _accept(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode()


def serve_terminal(handler, term_conf: dict) -> None:
    """Upgrade the connection to WebSocket and bridge it to a PTY shell. Blocks
    until the session ends. Never lets exceptions escape to the server."""
    import shutil
    import signal

    try:
        import pty
    except ImportError:  # non-unix
        handler.send_error(501, "pty unavailable on this platform")
        return

    key = handler.headers.get("Sec-WebSocket-Key")
    sock = handler.connection
    try:
        sock.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {_accept(key)}\r\n\r\n").encode())
    except OSError:
        return
    handler.close_connection = True  # we own the socket now

    shell = term_conf.get("shell") or os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
    try:
        pid, master = pty.fork()
    except OSError:
        return
    if pid == 0:  # child: the PTY slave is already our stdio
        try:
            os.chdir(os.path.expanduser("~"))
        except OSError:
            pass
        env = dict(os.environ, TERM="xterm-256color")
        try:
            os.execvpe(shell, [shell, "-i"], env)
        except OSError:
            os._exit(1)

    try:
        _bridge(sock, master)
    finally:
        try:
            os.close(master)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except (OSError, ChildProcessError):
            pass


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    import fcntl
    import termios

    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def _bridge(sock, master: int) -> None:
    buf = bytearray()
    while True:
        try:
            readable, _, _ = select.select([sock, master], [], [], 60)
        except (OSError, ValueError):
            break
        if master in readable:
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            try:
                _send(sock, data, 0x2)
            except OSError:
                break
        if sock in readable:
            try:
                chunk = sock.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buf.extend(chunk)
            while True:
                frame = _take_frame(buf)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:  # close
                    return
                if opcode == 0x9:  # ping -> pong
                    try:
                        _send(sock, payload, 0xA)
                    except OSError:
                        return
                elif opcode == 0x1:  # text frame = control (resize JSON)
                    try:
                        msg = json.loads(payload.decode("utf-8", "replace"))
                        if "cols" in msg and "rows" in msg:
                            _set_winsize(master, int(msg["rows"]), int(msg["cols"]))
                    except (ValueError, TypeError, KeyError):
                        pass
                elif opcode in (0x0, 0x2):  # binary frame = keystrokes -> the pty
                    try:
                        os.write(master, payload)
                    except OSError:
                        return


def _take_frame(buf: bytearray):
    """Pop one complete client→server WebSocket frame from ``buf`` (always masked).
    Returns ``(opcode, unmasked_payload)`` or ``None`` if more bytes are needed."""
    if len(buf) < 2:
        return None
    opcode = buf[0] & 0x0F
    masked = buf[1] & 0x80
    ln = buf[1] & 0x7F
    off = 2
    if ln == 126:
        if len(buf) < 4:
            return None
        ln = struct.unpack(">H", bytes(buf[2:4]))[0]
        off = 4
    elif ln == 127:
        if len(buf) < 10:
            return None
        ln = struct.unpack(">Q", bytes(buf[2:10]))[0]
        off = 10
    mask = b""
    if masked:
        if len(buf) < off + 4:
            return None
        mask = bytes(buf[off:off + 4])
        off += 4
    if len(buf) < off + ln:
        return None
    data = bytes(buf[off:off + ln])
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    del buf[:off + ln]
    return opcode, data


def _send(sock, data: bytes, opcode: int) -> None:
    n = len(data)
    hdr = bytearray([0x80 | opcode])
    if n < 126:
        hdr.append(n)
    elif n < 65536:
        hdr.append(126)
        hdr += struct.pack(">H", n)
    else:
        hdr.append(127)
        hdr += struct.pack(">Q", n)
    sock.sendall(bytes(hdr) + data)
