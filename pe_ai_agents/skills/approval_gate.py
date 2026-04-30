"""Approval Gate -- risk classification + human-in-the-loop pause.

Two inputs decide whether a tool call runs autonomously, prompts the
operator, or is denied:

  1. The tool's ``RiskLevel`` for the current ``env`` (the static policy
     table below), or the explicit ``risk`` on the ToolCall itself.
  2. The current ``TrustMode`` (LOW/MEDIUM/HIGH) for the workstream,
     loaded from ``conf/trust_mode.yml``.

LOW    -- gate every mutating tool call, regardless of risk.
MEDIUM -- gate only HIGH-risk calls and MEDIUM-risk calls in prod.
HIGH   -- gate only HIGH-risk calls.

Read-only tools (``RiskLevel.LOW``) always run silently in any mode.

For local development the human approver is supplied via callback. In K8s
the approver wires up to a chat / web prompt and writes its decision back
into the same callback shape.
"""

from __future__ import annotations

from typing import Callable

from pe_ai_agents.models.context import ResolvedContext, TrustMode
from pe_ai_agents.models.risk import RiskLevel, ToolCall


class ApprovalDenied(RuntimeError):
    """Raised when the gate refuses (or the human declines) a tool call."""


# Approver signature: (tool_call, ctx) -> bool
Approver = Callable[[ToolCall, ResolvedContext], bool]


def deny_all(_call: ToolCall, _ctx: ResolvedContext) -> bool:
    return False


def allow_all(_call: ToolCall, _ctx: ResolvedContext) -> bool:
    return True


# Default risk policy keyed on (tool, env). Tools not listed default to
# whatever risk the ToolCall declares (typically MEDIUM).
_POLICY: dict[tuple[str, str], RiskLevel] = {
    # Pipeline runners / mutations
    ("kedro_run", "predev"): RiskLevel.MEDIUM,
    ("kedro_run", "dev"): RiskLevel.MEDIUM,
    ("kedro_run", "prod"): RiskLevel.HIGH,
    ("argo_submit", "predev"): RiskLevel.MEDIUM,
    ("argo_submit", "dev"): RiskLevel.MEDIUM,
    ("argo_submit", "prod"): RiskLevel.HIGH,
    ("argo_retry", "predev"): RiskLevel.MEDIUM,
    ("argo_retry", "dev"): RiskLevel.MEDIUM,
    ("argo_retry", "prod"): RiskLevel.HIGH,
    # Risky downstream actions
    ("dep_push_to_mbox", "predev"): RiskLevel.HIGH,
    ("dep_push_to_mbox", "dev"): RiskLevel.HIGH,
    ("dep_push_to_mbox", "prod"): RiskLevel.HIGH,
    ("mlflow_promote", "predev"): RiskLevel.HIGH,
    ("mlflow_promote", "dev"): RiskLevel.HIGH,
    ("mlflow_promote", "prod"): RiskLevel.HIGH,
    ("conf_draft_pr_base", "predev"): RiskLevel.HIGH,
    ("conf_draft_pr_base", "prod"): RiskLevel.HIGH,
    # Read-only tools
    ("kedro_list", "predev"): RiskLevel.LOW,
    ("kedro_list", "dev"): RiskLevel.LOW,
    ("kedro_list", "prod"): RiskLevel.LOW,
    ("argo_poll", "predev"): RiskLevel.LOW,
    ("argo_poll", "dev"): RiskLevel.LOW,
    ("argo_poll", "prod"): RiskLevel.LOW,
    ("dqm_run_checks", "predev"): RiskLevel.LOW,
    ("dqm_run_checks", "dev"): RiskLevel.LOW,
    ("dqm_run_checks", "prod"): RiskLevel.LOW,
    ("pk_check", "predev"): RiskLevel.LOW,
    ("pk_check", "dev"): RiskLevel.LOW,
    ("pk_check", "prod"): RiskLevel.LOW,
    ("territory_qc_run", "predev"): RiskLevel.LOW,
    ("territory_qc_run", "dev"): RiskLevel.LOW,
    ("territory_qc_run", "prod"): RiskLevel.LOW,
    ("db_query", "predev"): RiskLevel.LOW,
    ("db_query", "dev"): RiskLevel.LOW,
    ("db_query", "prod"): RiskLevel.LOW,
    ("journey_load", "predev"): RiskLevel.LOW,
    ("journey_load", "dev"): RiskLevel.LOW,
    ("journey_load", "prod"): RiskLevel.LOW,
    ("conf_read", "predev"): RiskLevel.LOW,
    ("conf_read", "dev"): RiskLevel.LOW,
    ("conf_read", "prod"): RiskLevel.LOW,
}


class ApprovalGate:
    """Risk-classifies and gates a ToolCall using the trust mode."""

    def __init__(
        self,
        *,
        approver: Approver = deny_all,
        trust_mode: TrustMode = TrustMode.LOW,
    ) -> None:
        self._approver = approver
        self._trust = trust_mode

    @property
    def trust_mode(self) -> TrustMode:
        return self._trust

    def classify(self, call: ToolCall, ctx: ResolvedContext) -> RiskLevel:
        """Resolve effective risk for this call. Explicit HIGH on the call
        always wins so an agent can flag a one-off dangerous action."""
        if call.risk == RiskLevel.HIGH:
            return RiskLevel.HIGH
        return _POLICY.get((call.tool, ctx.env), call.risk)

    def _requires_human(self, risk: RiskLevel, ctx: ResolvedContext) -> bool:
        """Decide if a (risk, env, trust_mode) combination needs a human."""
        if risk == RiskLevel.LOW:
            return False
        if self._trust == TrustMode.LOW:
            # LOW trust = gate every mutation regardless of env.
            return True
        if self._trust == TrustMode.MEDIUM:
            # MEDIUM = HIGH always gates; MEDIUM gates in prod only.
            if risk == RiskLevel.HIGH:
                return True
            return ctx.is_prod()
        # HIGH trust = only the HIGH risk list gates.
        return risk == RiskLevel.HIGH

    def run(
        self,
        call: ToolCall,
        ctx: ResolvedContext,
        *,
        execute: Callable[[], object],
    ) -> tuple[object, str]:
        """Classify, gate, and (if allowed) execute. Returns (result, gate_status)."""
        risk = self.classify(call, ctx)

        if not self._requires_human(risk, ctx):
            label = "auto-low" if risk == RiskLevel.LOW else f"auto-{self._trust.value}"
            return execute(), label

        if not self._approver(call, ctx):
            raise ApprovalDenied(
                f"Tool {call.tool!r} denied by approver "
                f"(risk={risk.value}, env={ctx.env}, trust={self._trust.value})"
            )
        return execute(), "human-approved"
