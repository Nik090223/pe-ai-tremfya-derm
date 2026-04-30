"""QC Reviewer -- functional + business QC gate before Ops handoff.

Run-time inputs:
  - ``mlflow_run_id``: the candidate model run to review
  - candidate metric values supplied via constructor (in production these
    are pulled from the MLflow run; here we accept them directly so the
    test surface is small and obvious)

Compares each metric against the matching KPI's benchmark range. Any
out-of-band metric makes the agent fail with a human-readable summary.
The agent does NOT auto-promote -- promotion is an explicit HIGH gate.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.kpi_registry import KPIRegistry
from pe_ai_agents.skills.provenance import ProvenanceLedger


class QCReviewer(Agent):
    name = "qc_reviewer"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        kpis: KPIRegistry,
        mlflow_run_id: str,
        candidate_metrics: dict[str, float],
    ) -> None:
        self._kpis = kpis
        self._run_id = mlflow_run_id
        self._metrics = dict(candidate_metrics)
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "kpi_lookup": self._tool_lookup,
                "qc_compare": self._tool_compare,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        for kpi_id in self._metrics:
            yield ToolCall(
                actor=self.name,
                tool="kpi_lookup",
                args={"kpi_id": kpi_id, "brand": ctx.brand},
                risk=RiskLevel.LOW,
                rationale=f"resolve benchmark for {kpi_id}",
            )
        yield ToolCall(
            actor=self.name,
            tool="qc_compare",
            args={"mlflow_run_id": self._run_id, "metrics": self._metrics},
            risk=RiskLevel.LOW,
            rationale="compare candidate metrics against benchmarks",
        )

    def _tool_lookup(self, *, kpi_id: str, brand: str) -> dict:
        try:
            kpi = self._kpis.get(kpi_id)
        except KeyError:
            return {"kpi_id": kpi_id, "found": False}
        return {
            "kpi_id": kpi_id,
            "found": True,
            "applies": kpi.applies_to(brand),
            "benchmark": (
                {"min": kpi.benchmark.min, "max": kpi.benchmark.max}
                if kpi.benchmark
                else None
            ),
        }

    def _tool_compare(self, *, mlflow_run_id: str, metrics: dict) -> dict:
        ok = True
        rows = []
        for kpi_id, value in metrics.items():
            try:
                kpi = self._kpis.get(kpi_id)
                bench = kpi.benchmark
                in_range = bool(bench and bench.contains(value))
            except KeyError:
                bench = None
                in_range = False
            rows.append(
                {
                    "kpi_id": kpi_id,
                    "value": value,
                    "in_range": in_range,
                    "benchmark": (
                        {"min": bench.min, "max": bench.max} if bench else None
                    ),
                }
            )
            if not in_range:
                ok = False
        return {"mlflow_run_id": mlflow_run_id, "ok": ok, "rows": rows}
