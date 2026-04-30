"""Argo adapter -- wraps ``master_argo_workflow.utils.argo_utility``.

In production: uses ``argo_utility.submit_workflow`` /
``query_workflow_status`` etc. In the harness: the in-memory ``FakeArgo``
returns deterministic states so tests pass without an Argo cluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ArgoState(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


@dataclass
class ArgoRun:
    run_id: str
    workflow_template: str
    parameters: dict = field(default_factory=dict)
    state: ArgoState = ArgoState.PENDING
    failed_node: str | None = None


class FakeArgo:
    """In-memory Argo substitute used by tests and the local CLI."""

    def __init__(self, *, fail_templates: tuple[str, ...] = ()) -> None:
        self._fail = set(fail_templates)
        self._runs: dict[str, ArgoRun] = {}
        self._counter = 0

    def submit(self, *, workflow_template: str, parameters: dict | None = None) -> ArgoRun:
        self._counter += 1
        run_id = f"argo-{workflow_template}-{self._counter:04d}"
        run = ArgoRun(
            run_id=run_id,
            workflow_template=workflow_template,
            parameters=dict(parameters or {}),
            state=ArgoState.RUNNING,
        )
        self._runs[run_id] = run
        return run

    def poll(self, run_id: str) -> ArgoRun:
        run = self._runs[run_id]
        if run.state == ArgoState.RUNNING:
            if run.workflow_template in self._fail:
                run.state = ArgoState.FAILED
                run.failed_node = f"{run.workflow_template}.node_1"
            else:
                run.state = ArgoState.SUCCEEDED
        return run

    def retry(self, run_id: str) -> ArgoRun:
        run = self._runs[run_id]
        run.state = ArgoState.RUNNING
        run.failed_node = None
        return run
