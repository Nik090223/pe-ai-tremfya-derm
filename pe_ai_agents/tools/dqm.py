"""DQM adapter -- wraps ``src/spc/pipelines/wrapper_utils/dqm_wrapper.py``.

DQM (Data Quality Monitoring) checks are read-only and produce a list of
findings the QC Watcher / QC Reviewer agents consume. In the harness we
stub a small set of checks so behaviour can be tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal["info", "warn", "critical"]


@dataclass
class DQMFinding:
    check: str
    table: str
    severity: Severity
    detail: str


class FakeDQM:
    """Deterministic DQM stub.

    ``inject_findings`` lets tests force specific findings to be returned
    on the next ``run_checks`` call.
    """

    def __init__(self) -> None:
        self._next: list[DQMFinding] = []

    def inject(self, findings: list[DQMFinding]) -> None:
        self._next = list(findings)

    def run_checks(self, *, brand: str, env: str) -> list[DQMFinding]:
        out, self._next = self._next, []
        return out


class FakePrimaryKeyChecker:
    """Stub for ``pipelines/utils/primary_key_check/``."""

    def __init__(self) -> None:
        self._next: dict[str, bool] = {}

    def set_result(self, table: str, ok: bool) -> None:
        self._next[table] = ok

    def check(self, *, table: str) -> dict:
        ok = self._next.pop(table, True)
        return {"table": table, "ok": ok}


class FakeTerritoryQC:
    """Stub for ``spc/fulfillment/qc_dashboard/territory_and_account_cover``."""

    NUM_CHECKS = 27

    def __init__(self) -> None:
        self._failing: set[int] = set()

    def fail(self, *check_indices: int) -> None:
        self._failing.update(check_indices)

    def run(self, *, brand: str) -> dict:
        results = []
        for i in range(self.NUM_CHECKS):
            results.append({"check": f"territory_qc_{i:02d}", "ok": i not in self._failing})
        return {
            "brand": brand,
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
            "results": results,
        }
