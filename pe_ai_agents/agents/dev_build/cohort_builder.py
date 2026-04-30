"""Cohort Builder -- defines and validates a patient cohort.

Anchors on a chosen event (referral or shipment), applies indication
rules (PsO / PsA), and reports cohort size + per-indication counts. The
resulting cohort spec is written to provenance so downstream agents
(Feature Builder, Model Builder) can attest against it.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.journey import FakeJourneyLog


class CohortBuilder(Agent):
    name = "cohort_builder"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        journey: FakeJourneyLog,
        anchor_event: str = "referral",
    ) -> None:
        self._journey = journey
        self._anchor = anchor_event
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "journey_load": self._tool_load,
                "cohort_summarize": self._tool_summarize,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        for sub in ctx.sub_indications:
            yield ToolCall(
                actor=self.name,
                tool="journey_load",
                args={"brand": ctx.brand, "indication": sub},
                risk=RiskLevel.LOW,
                rationale=f"load journey events for {sub}",
            )
        yield ToolCall(
            actor=self.name,
            tool="cohort_summarize",
            args={"anchor": self._anchor},
            risk=RiskLevel.LOW,
            rationale="summarize cohort sizes per sub-indication",
        )

    def _tool_load(self, *, brand: str, indication: str) -> dict:
        events = self._journey.load(brand=brand, indication=indication)
        anchored = [e for e in events if e.event_type == self._anchor]
        self._last_anchored = anchored
        unique_patients = {e.patient_id for e in anchored}
        return {
            "indication": indication,
            "n_events": len(events),
            "n_anchored": len(anchored),
            "n_patients": len(unique_patients),
        }

    def _tool_summarize(self, *, anchor: str) -> dict:
        # Use whatever the last load left in memory; in real life this
        # would consume a deterministic intermediate cohort table.
        anchored = getattr(self, "_last_anchored", [])
        per_ind = Counter(e.indication for e in anchored)
        return {
            "anchor_event": anchor,
            "per_indication": dict(per_ind),
            "total_patients": len({e.patient_id for e in anchored}),
        }
