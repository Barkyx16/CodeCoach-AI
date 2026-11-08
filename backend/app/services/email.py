"""Outgoing email behind a tiny interface, so the app never depends on one provider.

- ConsoleEmailSender: logs the message (development).
- FileEmailSender: writes each message as JSON to a directory (tests and end-to-end tests read
  the reset link from there).
- SmtpEmailSender: real delivery over SMTP (production). Works with any provider's SMTP service.
  The connection is encrypted (STARTTLS or implicit TLS) and the server's certificate and
  hostname are always verified.

What a successful `send` means: the mail server *accepted* the message (an SMTP 250). Not that it
was delivered, and not that anyone read it. Failures are typed so the outbox can tell a permanent
refusal (retrying won't help) from a temporary problem (it will retry).

Production refuses console/file (see Settings): they'd put password-reset links in logs or on
disk.
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
import sys
import time
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from typing import Protocol, TextIO

from app.config import Settings

logger = logging.getLogger("codecoach.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    # Set by the outbox (one per job), so a provider's logs and events can be matched to the job.
    message_id: str | None = None


class EmailRejectedError(Exception):
    """The mail server refused this message for good (a 5xx answer). Retrying won't help.
    The message names the SMTP code only: a server's text can echo the address."""


class EmailConfigurationError(Exception):
    """The mail server refused our sign-in (wrong SMTP username or password). An operator has to
    fix the settings; jobs keep retrying with backoff meanwhile."""


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    """Development only (production refuses it): nothing is sent. The email is printed to the
    terminal running the server as a plain, readable block, so a verification code or reset link
    can be copied from there."""

    def __init__(self, stream: TextIO | None = None):
        self.stream = stream

    def send(self, email: Email) -> None:
        logger.info(
            "email (console backend, not delivered)", extra={"to": email.to, "subject": email.subject}
        )
        rule = "─" * 72
        lines = [
            "",
            f"┌{rule}",
            "│ EMAIL (not sent: this server has no mail server set up; see docs/EMAIL.md)",
            f"│ To:      {email.to}",
            f"│ Subject: {email.subject}",
            "│",
            *(f"│ {line}" for line in email.text.splitlines()),
            f"└{rule}",
            "",
        ]
        stream = self.stream or sys.stderr
        stream.write("\n".join(lines) + "\n")
        stream.flush()


class FileEmailSender:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def send(self, email: Email) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{time.time_ns()}.json"
        path.write_text(json.dumps(asdict(email)))


def tls_context(settings: Settings) -> ssl.SSLContext:
    """Verifies the server's certificate chain and hostname (Python's default for smtplib does
    neither). SMTP_CA_BUNDLE adds a private CA; it never turns verification off."""
    return ssl.create_default_context(cafile=settings.smtp_ca_bundle or None)


class SmtpEmailSender:
    def __init__(
        self,
        settings: Settings,
        smtp_class: type[smtplib.SMTP] = smtplib.SMTP,
        smtp_ssl_class: type[smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
    ):
        self.settings = settings
        self.smtp_class = smtp_class
        self.smtp_ssl_class = smtp_ssl_class

    def _connect(self) -> smtplib.SMTP:
        s = self.settings
        assert s.smtp_host  # validated at startup
        context = tls_context(s)
        if s.smtp_tls_mode == "ssl":
            return self.smtp_ssl_class(
                s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=context
            )
        smtp = self.smtp_class(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
        if s.smtp_tls_mode == "starttls":
            try:
                smtp.starttls(context=context)
            except BaseException:
                smtp.close()
                raise
        return smtp

    def check(self) -> list[str]:
        """Connect, encrypt and sign in, sending nothing. Returns the stages reached; raises on
        the first failure."""
        s = self.settings
        reached = []
        with self._connect() as smtp:
            reached.append("connected")
            if s.smtp_tls_mode != "none":
                reached.append("encrypted, certificate verified")
            if s.smtp_username and s.smtp_password:
                self._login(smtp)
                reached.append("signed in")
            smtp.noop()
        return reached

    def _login(self, smtp: smtplib.SMTP) -> None:
        s = self.settings
        assert s.smtp_username and s.smtp_password
        try:
            smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailConfigurationError(f"the mail server refused the sign-in ({exc.smtp_code})") from None

    def send(self, email: Email) -> None:
        s = self.settings
        msg = EmailMessage()
        msg["From"] = s.email_from
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg["Date"] = formatdate(localtime=False)
        if email.message_id:
            msg["Message-ID"] = email.message_id
        msg.set_content(email.text)
        try:
            with self._connect() as smtp:
                if s.smtp_username and s.smtp_password:
                    self._login(smtp)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            codes = sorted({code for code, _ in exc.recipients.values()})
            if codes and all(500 <= c < 600 for c in codes):
                raise EmailRejectedError(f"the mail server refused the recipient ({codes[0]})") from None
            raise TemporaryEmailError(
                f"the mail server deferred the recipient ({codes[0] if codes else '?'})"
            ) from None
        except smtplib.SMTPResponseException as exc:
            if 500 <= exc.smtp_code < 600:
                raise EmailRejectedError(f"the mail server refused the message ({exc.smtp_code})") from None
            raise TemporaryEmailError(f"the mail server deferred the message ({exc.smtp_code})") from None


class TemporaryEmailError(Exception):
    """A 4xx answer: the mail server asked us to try again later."""


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    if settings.email_backend == "file":
        return FileEmailSender(settings.email_file_dir)
    return ConsoleEmailSender()


def check_email(settings: Settings, *, connect: bool = False, send_to: str | None = None, out=print) -> int:
    """What `python -m app.cli check-email` reports. Names and presence only, never a value.
    `connect` signs in without sending; `send_to` sends ONE test message (an operator's explicit
    choice). Returns 0 when everything asked for worked."""
    out(f"EMAIL_BACKEND: {settings.email_backend}")
    if settings.email_backend != "smtp":
        out(
            "Nothing is sent: this backend prints (console) or saves (file) emails instead. "
            "Set EMAIL_BACKEND=smtp and the SMTP_* settings to send (docs/EMAIL.md)."
        )
        return 1
    present = lambda v: "set" if v else "NOT SET"  # noqa: E731
    out(f"SMTP_HOST: {present(settings.smtp_host)}   SMTP_PORT: {settings.smtp_port}")
    out(f"SMTP_SECURITY: {settings.smtp_tls_mode}   SMTP_CA_BUNDLE: {present(settings.smtp_ca_bundle)}")
    out(
        f"SMTP_USERNAME: {present(settings.smtp_username)}   SMTP_PASSWORD: {present(settings.smtp_password)}"
    )
    from app.config import _address_domain

    out(f"EMAIL_FROM domain: {_address_domain(settings.email_from) or 'NONE'}")
    if not settings.smtp_host:
        out("Blocked: SMTP_HOST is not set.")
        return 1
    if not (connect or send_to):
        out("Configuration read. Add --connect to sign in to the mail server (nothing is sent).")
        return 0
    sender = SmtpEmailSender(settings)
    try:
        for stage in sender.check():
            out(f"ok: {stage}")
    except Exception as exc:  # noqa: BLE001 - an operator diagnostic: say what failed, not the secret
        out(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    if send_to:
        try:
            sender.send(
                Email(
                    to=send_to,
                    subject="CodeCoach AI test email",
                    text="This is a test email from CodeCoach AI's check-email command. Nothing else to do.\n",
                )
            )
        except Exception as exc:  # noqa: BLE001
            out(f"FAILED to send the test email: {type(exc).__name__}: {exc}")
            return 1
        out(
            "ok: the mail server ACCEPTED the test email. That is not proof of delivery: "
            "check that it arrived in the inbox (and not in spam)."
        )
    return 0
