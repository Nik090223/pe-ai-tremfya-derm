"""MLflow tracking skill -- thin adapter over ``mlflow_utils.py``.

In production this wraps the existing
``src/spc/pipelines/wrapper_utils/mlflow_utils.py``. In the harness the
default implementation is an in-memory stub so tests run with no MLflow
server. Real adapters subclass ``MLflowTracker`` and override the four
methods.

Why this lives as a skill (not a tool): both Retrainer and Model Builder
agents need uniform experiment logging behaviour. Keeping it as a skill
avoids two tools growing diverging conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MLflowRun:
    run_id: str
    experiment: str
    started_at: str
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    stage: str = "None"  # None | Staging | Production | Archived
    ended_at: str | None = None


class MLflowTracker:
    """In-memory stub of MLflow; swap for a real adapter in prod."""

    def __init__(self) -> None:
        self._runs: dict[str, MLflowRun] = {}
        self._counter = 0

    # --- Run lifecycle -------------------------------------------------

    def start_run(self, *, experiment: str, params: dict[str, Any] | None = None) -> MLflowRun:
        self._counter += 1
        run_id = f"mlflow-{self._counter:04d}"
        run = MLflowRun(
            run_id=run_id,
            experiment=experiment,
            started_at=datetime.now(timezone.utc).isoformat(),
            params=dict(params or {}),
        )
        self._runs[run_id] = run
        return run

    def log_metrics(self, run_id: str, metrics: dict[str, float]) -> None:
        self._runs[run_id].metrics.update(metrics)

    def end_run(self, run_id: str) -> None:
        self._runs[run_id].ended_at = datetime.now(timezone.utc).isoformat()

    # --- Stage promotion (gated upstream) ------------------------------

    def promote(self, run_id: str, *, to_stage: str) -> MLflowRun:
        if to_stage not in ("Staging", "Production", "Archived"):
            raise ValueError(f"unknown stage {to_stage!r}")
        run = self._runs[run_id]
        run.stage = to_stage
        return run

    # --- Read access --------------------------------------------------

    def get(self, run_id: str) -> MLflowRun:
        return self._runs[run_id]

    def list(self, *, experiment: str | None = None) -> list[MLflowRun]:
        runs = list(self._runs.values())
        if experiment:
            runs = [r for r in runs if r.experiment == experiment]
        return runs
