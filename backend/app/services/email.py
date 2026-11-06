"""Outgoing email behind a tiny interface, so the app never depends on one provider.

- ConsoleEmailSender: logs the message (development).
- FileEmailSender: writes each message as JSON to a directory (tests and end-to-end tests read
  the reset link from there).
- SmtpEmailSender: real delivery over SMTP with STARTTLS (production).

Production refuses console/file (see Settings): they'd put password-reset links in logs or on
disk.
"""

from __future__ import annotations

import json
import logging
import smtplib
import time
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from app.config import Settings

logger = logging.getLogger("codecoach.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleEmailSender:
    def send(self, email: Email) -> None:
        logger.info(
            "email (console backend, not delivered)", extra={"to": email.to, "subject": email.subject}
        )
        logger.info("email body:\n%s", email.text)


class FileEmailSender:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def send(self, email: Email) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{time.time_ns()}.json"
        path.write_text(json.dumps(asdict(email)))


class SmtpEmailSender:
    def __init__(self, settings: Settings, smtp_class: type[smtplib.SMTP] = smtplib.SMTP):
        self.settings = settings
        self.smtp_class = smtp_class

    def send(self, email: Email) -> None:
        s = self.settings
        msg = EmailMessage()
        msg["From"] = s.email_from
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.text)
        assert s.smtp_host  # validated at startup
        with self.smtp_class(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username and s.smtp_password:
                smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
            smtp.send_message(msg)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    if settings.email_backend == "file":
        return FileEmailSender(settings.email_file_dir)
    return ConsoleEmailSender()
