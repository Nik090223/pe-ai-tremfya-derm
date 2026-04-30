"""QC Watcher -- always-on QC + alerting agent.

The Watcher runs the read-only QC checks and emits alerts to the
``runs/qc_state.json`` file the dashboard reads. Unlike the runners it
does not mutate pipeline state, so every tool call is RiskLevel.LOW.

The plan for one tick is:

  1. ``dqm_run_checks``     -- DQM findings on the brand's source tables
  2. ``pk_check``           -- primary-key sanity for the canonical view
  3. ``territory_qc_run``   -- the 27 territory/account checks

Findings above the configured severity are turned into AlertSink alerts.
The agent records its run + each emitted alert to provenance.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.agents.ops._kedro_runner import _KedroRunnerBase  # noqa: F401  (sibling import, not used)
from pe_ai_agents.models.context import ResolvedContext, WorkspaceContext, AgentResult
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.alerts import AlertSink, Severity
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.dqm import (
    DQMFinding,
    FakeDQM,
    FakePrimaryKeyChecker,
    FakeTerritoryQC,
)


PRIMARY_TABLE = "events_patient_journey_tremfya"


class QCWatcher(Agent):
    name = "qc_watcher"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        alerts: AlertSink,
        dqm: FakeDQM,
        pk: FakePrimaryKeyChecker,
        territory: FakeTerritoryQC,
    ) -> None:
        self._alerts = alerts
        self._dqm = dqm
        self._pk = pk
        self._territory = territory
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "dqm_run_checks": self._tool_dqm,
                "pk_check": self._tool_pk,
                "territory_qc_run": self._tool_territory,
            },
        )

    # --- Plan ---------------------------------------------------------

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        yield ToolCall(
            actor=self.name,
            tool="dqm_run_checks",
            args={"brand": ctx.brand, "env": ctx.env},
            risk=RiskLevel.LOW,
            rationale="DQM sweep over source tables",
        )
        yield ToolCall(
            actor=self.name,
            tool="pk_check",
            args={"table": PRIMARY_TABLE},
            risk=RiskLevel.LOW,
            rationale="primary-key sanity on canonical journey view",
        )
        yield ToolCall(
            actor=self.name,
            tool="territory_qc_run",
            args={"brand": ctx.brand},
            risk=RiskLevel.LOW,
            rationale="territory + account coverage QC (27 checks)",
        )

    # --- Tool wrappers (record + emit alerts) -------------------------

    def _tool_dqm(self, *, brand: str, env: str) -> dict:
        findings: list[DQMFinding] = self._dqm.run_checks(brand=brand, env=env)
        # Translate findings to alerts. WARN+ findings become alerts.
        for f in findings:
            if f.severity == "info":
                continue
            severity = Severity.CRITICAL if f.severity == "critical" else Severity.WARN
            self._alerts.emit(
                actor=self.name,
                code=f"dqm.{f.check}",
                message=f"{f.table}: {f.detail}",
                severity=severity,
                brand=brand,
                env=env,
                extra={"check": f.check, "table": f.table},
            )
        return {
            "n_findings": len(findings),
            "n_warn": sum(1 for f in findings if f.severity == "warn"),
            "n_critical": sum(1 for f in findings if f.severity == "critical"),
        }

    def _tool_pk(self, *, table: str) -> dict:
        result = self._pk.check(table=table)
        if not result["ok"]:
            self._alerts.emit(
                actor=self.name,
                code="pk.duplicates",
                message=f"primary-key check failed for {table}",
                severity=Severity.CRITICAL,
                extra={"table": table},
            )
        return result

    def _tool_territory(self, *, brand: str) -> dict:
        result = self._territory.run(brand=brand)
        if result["failed"] > 0:
            self._alerts.emit(
                actor=self.name,
                code="territory_qc.fails",
                message=f"{result['failed']} of {self._territory.NUM_CHECKS} territory checks failed",
                severity=Severity.WARN if result["failed"] < 5 else Severity.CRITICAL,
                brand=brand,
                extra={"failed_count": str(result["failed"])},
            )
        return {"passed": result["passed"], "failed": result["failed"]}

    # Override summary to surface alert count.
    def run(self, workspace: WorkspaceContext, request: str = "") -> AgentResult:
        before = len(self._alerts.read())
        result = super().run(workspace, request)
        after = len(self._alerts.read())
        result.summary += f"; alerts_emitted={after - before}"
        result.artifacts["alerts_emitted"] = after - before
        return result
