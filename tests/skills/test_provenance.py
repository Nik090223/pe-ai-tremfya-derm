"""Provenance ledger -- write/read/hash invariants."""

from __future__ import annotations

import json
from pathlib import Path


def test_record_round_trips(ledger, runs_dir: Path) -> None:
    entry = ledger.record(
        run_id="r1",
        actor="agentX",
        action="dispatch",
        inputs={"a": 1},
        outputs={"b": 2},
        gate_status="auto-low",
    )
    assert entry["actor"] == "agentX"
    assert entry["input_hash"]
    assert entry["output_hash"]

    rows = ledger.read("r1")
    assert len(rows) == 1
    assert rows[0]["action"] == "dispatch"
    assert rows[0]["gate_status"] == "auto-low"


def test_record_appends(ledger) -> None:
    for i in range(3):
        ledger.record(run_id="r2", actor="x", action=f"step{i}")
    rows = ledger.read("r2")
    assert [r["action"] for r in rows] == ["step0", "step1", "step2"]


def test_record_handles_no_payload(ledger) -> None:
    entry = ledger.record(run_id="r3", actor="x", action="dispatch")
    assert entry["input_hash"] is None
    assert entry["output_hash"] is None


def test_list_runs(ledger) -> None:
    ledger.record(run_id="ra", actor="x", action="a")
    ledger.record(run_id="rb", actor="x", action="b")
    assert ledger.list_runs() == ["ra", "rb"]


def test_jsonl_is_one_object_per_line(ledger, runs_dir: Path) -> None:
    ledger.record(run_id="rc", actor="x", action="a")
    ledger.record(run_id="rc", actor="x", action="b")
    p = runs_dir / "rc" / "provenance.jsonl"
    lines = [line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        json.loads(line)
