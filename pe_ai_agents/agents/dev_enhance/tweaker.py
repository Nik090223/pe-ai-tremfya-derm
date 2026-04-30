"""Tweaker -- small scoped pipeline edits.

Reads a target ``conf/.../*.yml`` file, computes a diff with the proposed
text, and drafts a sandboxed PR. Edits to ``conf/base/*`` are HIGH risk
and gated by ``conf_draft_pr_base``; brand-scoped edits are MEDIUM.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.conf import FakeConf


class Tweaker(Agent):
    name = "tweaker"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        conf: FakeConf,
        target_path: str,
        proposed_yaml: str,
    ) -> None:
        self._conf = conf
        self._target = target_path
        self._proposed = proposed_yaml
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "conf_read": self._tool_read,
                "conf_diff": self._tool_diff,
                "conf_draft_pr_base": self._tool_draft_base,
                "conf_draft_pr_brand": self._tool_draft_brand,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        yield ToolCall(
            actor=self.name,
            tool="conf_read",
            args={"path": self._target},
            risk=RiskLevel.LOW,
            rationale="read current YAML before drafting an edit",
        )
        yield ToolCall(
            actor=self.name,
            tool="conf_diff",
            args={"path": self._target, "proposed": self._proposed},
            risk=RiskLevel.LOW,
            rationale="produce a unified diff for review",
        )
        # Pick the right gate keyed on whether this is a base/* edit.
        is_base = self._target.startswith("conf/base/")
        tool = "conf_draft_pr_base" if is_base else "conf_draft_pr_brand"
        yield ToolCall(
            actor=self.name,
            tool=tool,
            args={"path": self._target, "proposed": self._proposed},
            rationale="draft sandbox PR for human review",
        )

    def _tool_read(self, *, path: str) -> dict:
        return {"path": path, "content": self._conf.read(path)}

    def _tool_diff(self, *, path: str, proposed: str) -> dict:
        return {"path": path, "diff": self._conf.diff(path, proposed)}

    def _tool_draft_base(self, *, path: str, proposed: str) -> dict:
        draft = self._conf.draft_pr(path=path, proposed=proposed)
        return {"path": draft.file_path, "diff": draft.unified_diff(), "scope": "base"}

    def _tool_draft_brand(self, *, path: str, proposed: str) -> dict:
        draft = self._conf.draft_pr(path=path, proposed=proposed)
        return {"path": draft.file_path, "diff": draft.unified_diff(), "scope": "brand"}
