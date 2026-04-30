"""Risk classification for tool calls and the gate matrix."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """Tool-call risk classification.

    LOW    -- read-only or trivially reversible; never gated.
    MEDIUM -- mutates state in dev/predev only; gated in prod (or always in
              LOW trust mode).
    HIGH   -- always gated regardless of environment or trust mode.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ToolCall:
    """Immutable description of a tool invocation an agent wants to make.

    Agents emit ToolCall objects; the runtime risk-classifies them, the
    approval gate consults the policy + trust mode, and only then does the
    call execute. Every ToolCall is recorded to the provenance ledger.
    """

    actor: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    risk: RiskLevel = RiskLevel.MEDIUM
    rationale: str = ""

    def with_risk(self, risk: RiskLevel) -> "ToolCall":
        return ToolCall(
            actor=self.actor,
            tool=self.tool,
            args=self.args,
            risk=risk,
            rationale=self.rationale,
        )
