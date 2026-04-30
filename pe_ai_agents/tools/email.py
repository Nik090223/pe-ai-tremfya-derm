"""Email adapter -- wraps ``send_email_notification.py``.

Real adapter posts via the existing SMTP utility. ``FakeEmailNotifier``
just records sent messages so tests can assert on them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailRecord:
    subject: str
    body: str


class FakeEmailNotifier:
    def __init__(self) -> None:
        self.sent: list[EmailRecord] = []

    def __call__(self, subject: str, body: str) -> None:
        self.sent.append(EmailRecord(subject=subject, body=body))
