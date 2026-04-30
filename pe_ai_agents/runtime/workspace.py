"""Workspace -- the harness's user-facing entry point.

Each (brand, workstream) cell is a workspace. A workspace:

  - resolves the brand context (brand_context.resolve)
  - loads the trust mode for its workstream (runtime.trust_mode)
  - constructs a single shared ApprovalGate, ProvenanceLedger,
    AlertSink, MLflowTracker, KPIRegistry that the workspace's agents
    share (so all provenance/alerts land in the same files)
  - exposes ``invoke(agent, request)`` to run a registered agent

Workspaces are NOT routers -- the user picks the agent. Workspaces just
remove the boilerplate of wiring each agent up by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

from pe_ai_agents.models.context import (
    AgentResult,
    ResolvedContext,
    TrustMode,
    WorkspaceContext,
    Workstream,
    new_run_id,
)
from pe_ai_agents.models.risk import ToolCall
from pe_ai_agents.runtime import trust_mode as trust_mode_loader
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.alerts import AlertSink
from pe_ai_agents.skills.approval_gate import ApprovalGate, Approver, deny_all
from pe_ai_agents.skills.brand_context import resolve as resolve_brand
from pe_ai_agents.skills.kpi_registry import KPIRegistry
from pe_ai_agents.skills.mlflow_tracker import MLflowTracker
from pe_ai_agents.skills.provenance import ProvenanceLedger


def stdin_approver(call: ToolCall, ctx: ResolvedContext) -> bool:
    """Default approver -- prompts on stdin. Replace in tests / non-CLI runs."""
    print(
        f"\n[GATE] {call.actor} -> {call.tool}  (env={ctx.env}, brand={ctx.brand})"
    )
    if call.rationale:
        print(f"       rationale: {call.rationale}")
    if call.args:
        print(f"       args: {call.args}")
    answer = input("       approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


class Workspace:
    """One (workstream, brand) cell with a shared services bundle."""

    def __init__(
        self,
        *,
        workstream: Workstream,
        repo_root: Path | str = ".",
        run_type: str | None = None,
        env: str = "predev",
        approver: Approver = stdin_approver,
        trust: TrustMode | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.workstream = workstream

        # Trust mode: loaded from conf/trust_mode.yml unless overridden.
        self.trust = trust or trust_mode_loader.get(
            workstream,
            path=self.repo_root / "conf" / "trust_mode.yml",
        )

        # Shared services. Same instances are passed to every agent the
        # workspace constructs so all provenance lands in one ledger.
        self.ledger = ProvenanceLedger(runs_dir=self.repo_root / "runs")
        self.gate = ApprovalGate(approver=approver, trust_mode=self.trust)
        self.alerts = AlertSink(state_path=self.repo_root / "runs" / "qc_state.json")
        self.mlflow = MLflowTracker()
        self.kpis = KPIRegistry(root=self.repo_root / "conf" / "kpi_registry")

        # Per-invocation context: brand-resolved + run_id + trust.
        resolved = resolve_brand(run_type=run_type, env=env)
        self.context = WorkspaceContext(
            workstream=workstream,
            resolved=resolved,
            trust=self.trust,
        )

        # Agents registered in this workspace.
        self._agents: dict[str, Agent] = {}

    # --- Registration --------------------------------------------------

    def register(self, agent: Agent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"agent {agent.name!r} already registered")
        self._agents[agent.name] = agent

    def register_many(self, agents: Iterable[Agent]) -> None:
        for a in agents:
            self.register(a)

    def list_agents(self) -> list[str]:
        return sorted(self._agents)

    # --- Invocation ----------------------------------------------------

    def invoke(self, agent_name: str, request: str = "") -> AgentResult:
        if agent_name not in self._agents:
            raise KeyError(
                f"Unknown agent {agent_name!r}. Available: {self.list_agents()}"
            )
        return self._agents[agent_name].run(self.context, request)

    def new_run(self, run_type: str | None = None, env: str | None = None) -> WorkspaceContext:
        """Replace the current context with a new run_id (and optionally env/run_type)."""
        resolved = resolve_brand(
            run_type=run_type or self.context.resolved.run_type,
            env=env or self.context.resolved.env,
            run_id=new_run_id(),
        )
        self.context = WorkspaceContext(
            workstream=self.workstream,
            resolved=resolved,
            trust=self.trust,
        )
        return self.context
