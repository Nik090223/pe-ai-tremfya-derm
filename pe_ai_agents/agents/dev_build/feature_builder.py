"""Feature Builder -- drafts a feature into the YAML feature framework.

Reads ``conf/{brand}/data_engineering/parameters.yml``, produces a YAML
diff that introduces the proposed feature, and records the proposed KPI
metadata. Adding the feature for real is gated through ``Tweaker`` /
the conf approval flow.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.conf import FakeConf


class FeatureBuilder(Agent):
    name = "feature_builder"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        conf: FakeConf,
        feature_id: str,
        feature_yaml: str,
    ) -> None:
        self._conf = conf
        self._feature_id = feature_id
        self._yaml = feature_yaml
        self._target = "conf/tremfya/data_engineering/parameters.yml"
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "conf_read": self._tool_read,
                "feature_yaml_draft": self._tool_draft,
                "kpi_register_proposal": self._tool_kpi_proposal,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        yield ToolCall(
            actor=self.name,
            tool="conf_read",
            args={"path": self._target},
            risk=RiskLevel.LOW,
            rationale="read existing parameters before drafting",
        )
        yield ToolCall(
            actor=self.name,
            tool="feature_yaml_draft",
            args={"path": self._target, "feature_id": self._feature_id, "yaml": self._yaml},
            rationale="emit unified diff for the new feature",
        )
        yield ToolCall(
            actor=self.name,
            tool="kpi_register_proposal",
            args={"feature_id": self._feature_id, "brand": ctx.brand},
            risk=RiskLevel.LOW,
            rationale="record a KPI registration proposal for review",
        )

    def _tool_read(self, *, path: str) -> dict:
        return {"path": path, "content_present": bool(self._conf.read(path))}

    def _tool_draft(self, *, path: str, feature_id: str, yaml: str) -> dict:
        existing = self._conf.read(path)
        proposed = (existing.rstrip() + "\n" if existing else "") + yaml.strip() + "\n"
        draft = self._conf.draft_pr(path=path, proposed=proposed)
        return {
            "path": draft.file_path,
            "feature_id": feature_id,
            "diff": draft.unified_diff(),
        }

    def _tool_kpi_proposal(self, *, feature_id: str, brand: str) -> dict:
        # In a real adapter this would write a draft KPI yml under
        # conf/kpi_registry/_proposals/. Here we record a structured proposal.
        return {
            "feature_id": feature_id,
            "brand": brand,
            "status": "proposed",
            "next_step": "human-review-and-merge",
        }
