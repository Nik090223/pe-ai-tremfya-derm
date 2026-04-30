"""Alert sink -- emit, read, rolling truncation, email threshold."""

from __future__ import annotations

import json
from pathlib import Path

from pe_ai_agents.skills.alerts import AlertSink, Severity


def test_emit_round_trips(alerts: AlertSink) -> None:
    alerts.emit(actor="qc", code="qc.test", message="hello", severity=Severity.WARN)
    rows = alerts.read()
    assert len(rows) == 1
    assert rows[0].code == "qc.test"
    assert rows[0].severity == Severity.WARN


def test_emit_appends(alerts: AlertSink) -> None:
    for i in range(3):
        alerts.emit(actor="qc", code=f"qc.{i}", message="x")
    codes = [a.code for a in alerts.read()]
    assert codes == ["qc.0", "qc.1", "qc.2"]


def test_rolling_truncation(runs_dir: Path) -> None:
    sink = AlertSink(state_path=runs_dir / "qc_state.json", max_alerts=3)
    for i in range(5):
        sink.emit(actor="qc", code=f"qc.{i}", message="x")
    codes = [a.code for a in sink.read()]
    assert codes == ["qc.2", "qc.3", "qc.4"]


def test_email_only_for_threshold_or_higher(runs_dir: Path) -> None:
    sent: list[tuple[str, str]] = []
    sink = AlertSink(
        state_path=runs_dir / "qc_state.json",
        email_notify=lambda s, b: sent.append((s, b)),
        email_threshold=Severity.WARN,
    )
    sink.emit(actor="qc", code="qc.info", message="i", severity=Severity.INFO)
    sink.emit(actor="qc", code="qc.warn", message="w", severity=Severity.WARN)
    sink.emit(actor="qc", code="qc.crit", message="c", severity=Severity.CRITICAL)
    subjects = [s for s, _ in sent]
    assert len(sent) == 2
    assert any("WARN" in s for s in subjects)
    assert any("CRITICAL" in s for s in subjects)


def test_read_empty_when_no_file(runs_dir: Path) -> None:
    sink = AlertSink(state_path=runs_dir / "missing.json")
    assert sink.read() == []


def test_state_is_valid_json(alerts: AlertSink, runs_dir: Path) -> None:
    alerts.emit(actor="qc", code="qc.x", message="m", severity=Severity.CRITICAL)
    payload = json.loads((runs_dir / "qc_state.json").read_text(encoding="utf-8"))
    assert "alerts" in payload
    assert payload["alerts"][0]["severity"] == "critical"
