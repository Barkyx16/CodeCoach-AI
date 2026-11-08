"""A small, real SMTP server for tests: STARTTLS or implicit TLS with a throwaway self-signed
certificate, scripted answers (accept, refuse with 5xx, defer with 4xx), or silence (to test
timeouts). The app's real `smtplib` code talks to it over a socket. No message leaves the machine."""

from __future__ import annotations

import contextlib
import shutil
import socket
import ssl
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path


def make_certificate(directory: Path, common_name: str = "localhost") -> tuple[Path, Path]:
    """A self-signed certificate for `common_name` (and 127.0.0.1). Needs the openssl command."""
    if shutil.which("openssl") is None:
        raise RuntimeError("openssl is not installed")
    cert, key = directory / f"{common_name}.crt", directory / f"{common_name}.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            f"/CN={common_name}",
            "-addext",
            f"subjectAltName=DNS:{common_name},IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


@dataclass
class FakeSMTPServer:
    certfile: Path | None = None
    keyfile: Path | None = None
    implicit_tls: bool = False
    rcpt_reply: str = "250 2.1.5 OK"
    data_reply: str = "250 2.0.0 queued"
    auth_reply: str = "235 2.7.0 accepted"
    silent: bool = False  # accept the connection, never greet
    messages: list[bytes] = field(default_factory=list)
    sessions: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _tls(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        assert self.certfile and self.keyfile
        ctx.load_cert_chain(str(self.certfile), str(self.keyfile))
        return ctx

    def _serve(self) -> None:
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn: socket.socket) -> None:
        info: dict = {"tls": False, "auth": False}
        self.sessions.append(info)
        try:
            if self.silent:
                self._stop.wait(5)
                return
            if self.implicit_tls:
                conn = self._tls().wrap_socket(conn, server_side=True)
                info["tls"] = True
            reader = conn.makefile("rb")

            def say(line: str) -> None:
                conn.sendall(line.encode() + b"\r\n")

            say("220 fake.test ESMTP")
            while True:
                raw = reader.readline()
                if not raw:
                    return
                line = raw.decode(errors="replace").strip()
                verb = line.split(" ", 1)[0].upper()
                if verb in ("EHLO", "HELO"):
                    caps = ["250-fake.test"]
                    if self.certfile and not info["tls"]:
                        caps.append("250-STARTTLS")
                    caps.append("250 AUTH PLAIN LOGIN")
                    say("\r\n".join(caps))
                elif verb == "STARTTLS":
                    say("220 2.0.0 ready")
                    conn = self._tls().wrap_socket(
                        conn, server_side=True
                    )  # fails if the client refuses the cert
                    reader = conn.makefile("rb")
                    info["tls"] = True
                elif verb == "AUTH":
                    info["auth"] = True
                    say(self.auth_reply)
                elif verb == "MAIL":
                    say("250 2.1.0 OK")
                elif verb == "RCPT":
                    say(self.rcpt_reply)
                elif verb == "DATA":
                    say("354 end with <CRLF>.<CRLF>")
                    body = b""
                    while True:
                        chunk = reader.readline()
                        if chunk in (b".\r\n", b".\n", b""):
                            break
                        body += chunk
                    if self.data_reply.startswith("250"):
                        self.messages.append(body)
                    say(self.data_reply)
                elif verb in ("RSET", "NOOP"):
                    say("250 2.0.0 OK")
                elif verb == "QUIT":
                    say("221 2.0.0 bye")
                    return
                else:
                    say("502 5.5.2 not implemented")
        except (OSError, ssl.SSLError):
            return  # e.g. the client refused our certificate during the handshake
        finally:
            with contextlib.suppress(OSError):
                conn.close()

    def close(self) -> None:
        self._stop.set()
        self.sock.close()
