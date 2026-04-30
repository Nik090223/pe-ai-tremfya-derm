"""Kedro adapter -- thin wrapper around the PE.AI ``pipeline_registry``.

In production this calls into ``src/spc/pipeline_registry.py``. In the
harness the default is the in-memory ``FakeKedro`` so the agents and
tests run with no PE.AI source on disk.

A real adapter is expected to:

  - return the same shape from ``run`` and ``poll`` as the fake, so
    agents and tests don't need a separate code path
  - never raise on a known terminal state -- the agent decides what to
    do with FAILED / SUCCEEDED / RUNNING

To plug in the real Kedro session, swap ``FakeKedro`` for
``KedroAdapter`` in the workspace bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class KedroState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class KedroRun:
    run_id: str
    pipeline: str
    overrides: dict = field(default_factory=dict)
    state: KedroState = KedroState.PENDING
    failed_node: str | None = None


class PipelineNotConfigured(RuntimeError):
    """Raised when a brand-indication's pipeline is not yet wired in this repo."""


# ----- Default in-memory fake (used by tests and demos) -----

# Canonical pipelines this brand-indication exposes. Mirrors what
# ``src/spc/pipeline_registry.py`` registers in the live codebase.
PIPELINE_CATALOG = (
    "ds",                  # fulfillment + persistency scoring (config-selected)
    "ds_insights",
    "post_processing",     # aggregation + prioritization
    "territory_and_account_cover",
    "de",
    "fea",
    "mi",
    "int_persist",
)


class FakeKedro:
    """In-memory Kedro substitute. Deterministic for tests."""

    def __init__(self, *, fail_pipelines: tuple[str, ...] = ()) -> None:
        self._fail = set(fail_pipelines)
        self._runs: dict[str, KedroRun] = {}
        self._counter = 0

    def list_pipelines(self) -> list[str]:
        return list(PIPELINE_CATALOG)

    def run(self, *, pipeline: str, overrides: dict | None = None) -> KedroRun:
        if pipeline not in PIPELINE_CATALOG:
            raise PipelineNotConfigured(
                f"pipeline {pipeline!r} not in catalog: {PIPELINE_CATALOG}"
            )
        self._counter += 1
        run_id = f"kedro-{pipeline}-{self._counter:04d}"
        run = KedroRun(
            run_id=run_id,
            pipeline=pipeline,
            overrides=dict(overrides or {}),
            state=KedroState.RUNNING,
        )
        self._runs[run_id] = run
        return run

    def poll(self, run_id: str) -> KedroRun:
        run = self._runs[run_id]
        # Deterministic transition: RUNNING -> FAILED/SUCCEEDED on first poll.
        if run.state == KedroState.RUNNING:
            if run.pipeline in self._fail:
                run.state = KedroState.FAILED
                run.failed_node = f"{run.pipeline}.first_node"
            else:
                run.state = KedroState.SUCCEEDED
        return run
