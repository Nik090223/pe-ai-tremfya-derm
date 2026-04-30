"""Quick Analyst -- ad-hoc EDA on the patient journey.

Loads journey events for the brand's sub-indications, runs a small set
of read-only summaries (event counts, per-patient density, anchor->next
durations), and writes a short markdown brief to
``runs/<run_id>/quick_analysis.md`` for the analyst to share.

This agent is intentionally minimal: fast turnaround for client
hypotheses, no productionization side-effects.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.journey import FakeJourneyLog, JourneyEvent


class QuickAnalyst(Agent):
    name = "quick_analyst"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        journey: FakeJourneyLog,
        runs_dir: Path | str,
        question: str = "",
    ) -> None:
        self._journey = journey
        self._runs_dir = Path(runs_dir)
        self._question = question
        self._events: list[JourneyEvent] = []
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "journey_load": self._tool_load,
                "eda_summarize": self._tool_summarize,
                "write_brief": self._tool_brief,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        for sub in ctx.sub_indications:
            yield ToolCall(
                actor=self.name,
                tool="journey_load",
                args={"brand": ctx.brand, "indication": sub},
                risk=RiskLevel.LOW,
            )
        yield ToolCall(
            actor=self.name,
            tool="eda_summarize",
            risk=RiskLevel.LOW,
            rationale="event-type counts + per-patient density",
        )
        yield ToolCall(
            actor=self.name,
            tool="write_brief",
            args={"run_id": ctx.run_id, "brand": ctx.brand},
            risk=RiskLevel.LOW,
            rationale=f"render markdown brief for: {self._question or '(unspecified)'}",
        )

    def _tool_load(self, *, brand: str, indication: str) -> dict:
        events = self._journey.load(brand=brand, indication=indication)
        self._events.extend(events)
        return {"indication": indication, "n_events": len(events)}

    def _tool_summarize(self) -> dict:
        if not self._events:
            return {"event_counts": {}, "patients": 0}
        per_type = Counter(e.event_type for e in self._events)
        per_patient: dict[str, int] = defaultdict(int)
        for e in self._events:
            per_patient[e.patient_id] += 1
        densities = list(per_patient.values())
        avg_density = sum(densities) / len(densities)
        return {
            "event_counts": dict(per_type),
            "patients": len(per_patient),
            "avg_events_per_patient": round(avg_density, 2),
        }

    def _tool_brief(self, *, run_id: str, brand: str) -> dict:
        summary = self._tool_summarize()
        out_path = self._runs_dir / run_id / "quick_analysis.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Quick Analysis -- {brand} (run {run_id})",
            "",
            f"**Question:** {self._question or '(unspecified)'}",
            "",
            f"- Patients: {summary['patients']}",
            f"- Avg events / patient: {summary['avg_events_per_patient']}",
            "",
            "## Event-type counts",
            "",
            "| event | count |",
            "|---|---|",
        ]
        for ev, n in sorted(summary["event_counts"].items()):
            lines.append(f"| {ev} | {n} |")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"path": str(out_path), "summary": summary}
