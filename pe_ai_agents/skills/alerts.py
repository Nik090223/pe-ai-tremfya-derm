"""Alerts skill -- emits structured alerts the QC dashboard renders.

Alerts are written into two places:

  1. ``runs/qc_state.json`` -- a rolling state file the dashboard reads.
     The QC Watcher agent owns this file; other agents append via
     ``AlertSink.emit``. Old alerts are kept (``max_alerts`` defaults to
     500) so the dashboard's alert feed has scrollback.

  2. Optional email via ``email.notify`` for HIGH-severity alerts.

Severity scale: INFO < WARN < CRITICAL. Severity does not gate; it just
controls how the dashboard renders the alert and whether email goes out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class Alert:
    ts: str
    actor: str
    code: str            # short stable identifier, e.g. "qc.null_rate_high"
    message: str         # human-readable
    severity: Severity = Severity.INFO
    run_id: str | None = None
    brand: str | None = None
    env: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "actor": self.actor,
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "run_id": self.run_id,
            "brand": self.brand,
            "env": self.env,
            "extra": self.extra,
        }


EmailNotifier = Callable[[str, str], None]  # (subject, body) -> None


class AlertSink:
    """Append-rolling alert sink backed by a JSON file."""

    def __init__(
        self,
        state_path: Path | str,
        *,
        max_alerts: int = 500,
        email_notify: EmailNotifier | None = None,
        email_threshold: Severity = Severity.CRITICAL,
    ) -> None:
        self._path = Path(state_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max = max_alerts
        self._email = email_notify
        self._email_threshold = email_threshold

    def emit(
        self,
        *,
        actor: str,
        code: str,
        message: str,
        severity: Severity = Severity.INFO,
        run_id: str | None = None,
        brand: str | None = None,
        env: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> Alert:
        alert = Alert(
            ts=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            code=code,
            message=message,
            severity=severity,
            run_id=run_id,
            brand=brand,
            env=env,
            extra=extra or {},
        )
        self._append(alert)
        if self._email and _severity_geq(severity, self._email_threshold):
            self._email(f"[PE.AI {severity.value.upper()}] {code}", message)
        return alert

    def read(self) -> list[Alert]:
        if not self._path.exists():
            return []
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return [_alert_from_dict(d) for d in data.get("alerts", [])]

    def _append(self, alert: Alert) -> None:
        existing = []
        if self._path.exists():
            try:
                state = json.loads(self._path.read_text(encoding="utf-8"))
                existing = state.get("alerts", [])
            except json.JSONDecodeError:
                existing = []
        existing.append(alert.to_dict())
        if len(existing) > self._max:
            existing = existing[-self._max :]
        self._path.write_text(
            json.dumps({"alerts": existing}, indent=2),
            encoding="utf-8",
        )


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARN: 1, Severity.CRITICAL: 2}


def _severity_geq(a: Severity, b: Severity) -> bool:
    return _SEVERITY_ORDER[a] >= _SEVERITY_ORDER[b]


def _alert_from_dict(d: dict) -> Alert:
    return Alert(
        ts=d["ts"],
        actor=d["actor"],
        code=d["code"],
        message=d["message"],
        severity=Severity(d.get("severity", "info")),
        run_id=d.get("run_id"),
        brand=d.get("brand"),
        env=d.get("env"),
        extra=d.get("extra", {}) or {},
    )
