"""Base Agent contract.

Every specialist agent subclasses ``Agent`` and implements ``_plan`` to
emit an ordered sequence of ``ToolCall``s. The base class:

  1. Records the dispatch in the provenance ledger.
  2. For each ToolCall, gates it through the ApprovalGate.
  3. If approved, executes the tool function from the agent's tool table.
  4. Records the result + gate status to provenance.
  5. Returns an ``AgentResult`` summary.

The deterministic-Python ``_plan`` is the LLM extension point: a Claude
Agent SDK loop that emits ``ToolCall`` objects can drop in here without
the gating/provenance code changing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable

from pe_ai_agents.models.context import (
    AgentResult,
    ResolvedContext,
    WorkspaceContext,
)
from pe_ai_agents.models.risk import ToolCall
from pe_ai_agents.skills.approval_gate import ApprovalDenied, ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger


class Agent(ABC):
    """Base class for every PE.AI agent."""

    name: str = "base"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        tools: dict[str, Callable[..., Any]],
    ) -> None:
        self._gate = gate
        self._ledger = ledger
        self._tools = tools

    # --- Public API ----------------------------------------------------

    def run(self, workspace: WorkspaceContext, request: str = "") -> AgentResult:
        """Plan -> gate -> execute -> record loop. Returns AgentResult."""
        ctx = workspace.resolved
        artifacts: dict[str, Any] = {}
        denied: list[str] = []

        self._ledger.record(
            run_id=ctx.run_id,
            actor=self.name,
            action="dispatch",
            inputs={"request": request, "brand": ctx.brand, "env": ctx.env},
            workstream=workspace.workstream.value,
            brand=ctx.brand,
            env=ctx.env,
        )

        for call in self._plan(ctx, request):
            try:
                result, gate_status = self._gate.run(
                    call,
                    ctx,
                    execute=lambda c=call: self._dispatch(c),
                )
            except ApprovalDenied as exc:
                denied.append(call.tool)
                self._ledger.record(
                    run_id=ctx.run_id,
                    actor=self.name,
                    action=f"tool:{call.tool}",
                    inputs=call.args,
                    outputs={"error": str(exc)},
                    gate_status="denied",
                    workstream=workspace.workstream.value,
                    brand=ctx.brand,
                    env=ctx.env,
                )
                # Soft-fail: keep going so we still record what _was_ attempted.
                continue

            artifacts[call.tool] = result
            self._ledger.record(
                run_id=ctx.run_id,
                actor=self.name,
                action=f"tool:{call.tool}",
                inputs=call.args,
                outputs=result,
                gate_status=gate_status,
                workstream=workspace.workstream.value,
                brand=ctx.brand,
                env=ctx.env,
            )

        return self._summarize(ctx, request, artifacts, denied)

    # --- Subclass extension points ------------------------------------

    @abstractmethod
    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        """Emit the ordered sequence of ToolCalls.

        LLM extension point: replace this with a Claude Agent SDK loop
        that emits ToolCall objects. Gating + provenance is unchanged.
        """

    def _summarize(
        self,
        ctx: ResolvedContext,
        request: str,
        artifacts: dict[str, Any],
        denied: list[str],
    ) -> AgentResult:
        ok = not denied
        bits = [f"{k}: ok" for k in artifacts]
        if denied:
            bits.append(f"denied: {', '.join(denied)}")
        return AgentResult(
            actor=self.name,
            ok=ok,
            summary="; ".join(bits) or "no calls",
            artifacts=artifacts,
            denied_calls=denied,
        )

    # --- Private -------------------------------------------------------

    def _dispatch(self, call: ToolCall) -> Any:
        if call.tool not in self._tools:
            raise KeyError(f"Agent {self.name!r} has no tool {call.tool!r}")
        return self._tools[call.tool](**call.args)
