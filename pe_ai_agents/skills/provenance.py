"""Append-only JSONL provenance ledger.

Every agent action -- tool call, gate decision, agent dispatch, alert --
is appended as one JSON line to ``runs/<run_id>/provenance.jsonl``. The
QC dashboard and audit reviews consume this file.

Design decisions:
- Append-only: never edit or delete past entries.
- Hashes (not raw payloads) are recorded for inputs/outputs so the ledger
  is compact and PII-safe at trace time.
- One file per run_id keeps replay/debug simple.
- Records also include workstream + brand + env so the dashboard can
  filter without joining against a separate index.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _hash(payload: Any) -> str:
    """Stable SHA-256 prefix of a JSON-serialisable payload (dataclasses ok)."""
    if is_dataclass(payload):
        payload = asdict(payload)
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


class ProvenanceLedger:
    """Append-only JSONL ledger keyed by run_id."""

    def __init__(self, runs_dir: Path | str = "runs") -> None:
        self._runs_dir = Path(runs_dir)
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / "provenance.jsonl"

    def record(
        self,
        *,
        run_id: str,
        actor: str,
        action: str,
        inputs: Any = None,
        outputs: Any = None,
        rule_version: str = "n/a",
        gate_status: str = "n/a",
        workstream: str | None = None,
        brand: str | None = None,
        env: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one provenance entry. Returns the entry written."""
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "actor": actor,
            "action": action,
            "input_hash": _hash(inputs) if inputs is not None else None,
            "output_hash": _hash(outputs) if outputs is not None else None,
            "rule_version": rule_version,
            "gate_status": gate_status,
        }
        if workstream:
            entry["workstream"] = workstream
        if brand:
            entry["brand"] = brand
        if env:
            entry["env"] = env
        if extra:
            entry["extra"] = extra

        path = self._path_for(run_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + os.linesep)
        return entry

    def read(self, run_id: str) -> list[dict[str, Any]]:
        path = self._path_for(run_id)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def list_runs(self) -> list[str]:
        if not self._runs_dir.exists():
            return []
        return sorted(p.name for p in self._runs_dir.iterdir() if p.is_dir())
