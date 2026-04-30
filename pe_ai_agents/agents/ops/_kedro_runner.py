"""Shared base for Ops agents that drive a single Kedro pipeline.

The three scoring/aggregation runners share the same pattern:

  1. ``kedro_list``    -- read-only, confirm the pipeline is in catalog
  2. ``kedro_run``     -- mutating, gated; submit the pipeline
  3. ``kedro_poll``    -- read-only, poll until terminal

Subclasses just declare ``pipeline_name`` and (optionally) any overrides
to pass into ``kedro_run``.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.kedro import FakeKedro


class _KedroRunnerBase(Agent):
    """Run-and-poll base for the three Ops scoring/aggregation agents."""

    pipeline_name: str = ""  # subclasses must override

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        kedro: FakeKedro,
    ) -> None:
        self._kedro = kedro
        self._last_run_id: str | None = None
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "kedro_list": self._tool_list,
                "kedro_run": self._tool_run,
                "kedro_poll": self._tool_poll,
            },
        )

    # --- Plan ---------------------------------------------------------

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        yield ToolCall(
            actor=self.name,
            tool="kedro_list",
            risk=RiskLevel.LOW,
            rationale="confirm pipeline is registered before submitting",
        )
        yield ToolCall(
            actor=self.name,
            tool="kedro_run",
            args={
                "pipeline": self.pipeline_name,
                "overrides": self._overrides(ctx),
            },
            rationale=f"run {self.pipeline_name!r} for {ctx.brand}-{ctx.indication}",
        )
        # Poll once for the synchronous fake; production would loop with
        # backoff until terminal state is reached.
        yield ToolCall(
            actor=self.name,
            tool="kedro_poll",
            risk=RiskLevel.LOW,
            rationale="check terminal state",
        )

    def _overrides(self, ctx: ResolvedContext) -> dict:
        """Subclasses override to supply pipeline-specific params."""
        return {
            "brand": ctx.brand,
            "indication": ctx.indication,
            "run_type": ctx.run_type,
            "env": ctx.env,
        }

    # --- Tools --------------------------------------------------------

    def _tool_list(self) -> dict:
        pipelines = self._kedro.list_pipelines()
        return {
            "pipelines": pipelines,
            "target_in_catalog": self.pipeline_name in pipelines,
        }

    def _tool_run(self, *, pipeline: str, overrides: dict) -> dict:
        run = self._kedro.run(pipeline=pipeline, overrides=overrides)
        self._last_run_id = run.run_id
        return {
            "kedro_run_id": run.run_id,
            "pipeline": run.pipeline,
            "state": run.state.value,
        }

    def _tool_poll(self) -> dict:
        if self._last_run_id is None:
            return {"kedro_run_id": None, "state": "no_run", "failed_node": None}
        run = self._kedro.poll(self._last_run_id)
        return {
            "kedro_run_id": run.run_id,
            "state": run.state.value,
            "failed_node": run.failed_node,
        }
