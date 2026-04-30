"""Approval gate -- trust-mode + risk policy decision matrix."""

from __future__ import annotations

import pytest

from pe_ai_agents.models.context import ResolvedContext, TrustMode
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.skills.approval_gate import ApprovalDenied, ApprovalGate, allow_all, deny_all
from pe_ai_agents.skills.brand_context import resolve as resolve_brand


def _ctx(env: str = "predev") -> ResolvedContext:
    return resolve_brand(env=env, run_id="t-1")


def test_low_tool_runs_silently_in_low_trust(gate_low_deny) -> None:
    call = ToolCall(actor="x", tool="kedro_list", risk=RiskLevel.LOW)
    out, status = gate_low_deny.run(call, _ctx(), execute=lambda: "ok")
    assert out == "ok"
    assert status == "auto-low"


def test_low_trust_gates_every_mutation_in_predev() -> None:
    gate = ApprovalGate(approver=deny_all, trust_mode=TrustMode.LOW)
    call = ToolCall(actor="x", tool="kedro_run", risk=RiskLevel.MEDIUM)
    with pytest.raises(ApprovalDenied):
        gate.run(call, _ctx("predev"), execute=lambda: "should_not_run")


def test_low_trust_gate_lets_human_approve() -> None:
    gate = ApprovalGate(approver=allow_all, trust_mode=TrustMode.LOW)
    call = ToolCall(actor="x", tool="kedro_run", risk=RiskLevel.MEDIUM)
    out, status = gate.run(call, _ctx("predev"), execute=lambda: "ran")
    assert out == "ran"
    assert status == "human-approved"


def test_medium_trust_skips_predev_mutations() -> None:
    gate = ApprovalGate(approver=deny_all, trust_mode=TrustMode.MEDIUM)
    call = ToolCall(actor="x", tool="kedro_run", risk=RiskLevel.MEDIUM)
    out, status = gate.run(call, _ctx("predev"), execute=lambda: "ran")
    assert out == "ran"
    assert status == "auto-medium"


def test_medium_trust_still_gates_prod_mediums() -> None:
    gate = ApprovalGate(approver=deny_all, trust_mode=TrustMode.MEDIUM)
    call = ToolCall(actor="x", tool="kedro_run", risk=RiskLevel.HIGH)
    with pytest.raises(ApprovalDenied):
        # kedro_run resolves to HIGH in prod via the policy table.
        gate.run(call, _ctx("prod"), execute=lambda: "no")


def test_high_trust_only_gates_high() -> None:
    gate = ApprovalGate(approver=deny_all, trust_mode=TrustMode.HIGH)
    medium_call = ToolCall(actor="x", tool="kedro_run", risk=RiskLevel.MEDIUM)
    out, _ = gate.run(medium_call, _ctx("predev"), execute=lambda: "ran")
    assert out == "ran"

    high_call = ToolCall(actor="x", tool="dep_push_to_mbox", risk=RiskLevel.MEDIUM)
    with pytest.raises(ApprovalDenied):
        gate.run(high_call, _ctx("predev"), execute=lambda: "no")


def test_explicit_high_on_call_always_gates() -> None:
    gate = ApprovalGate(approver=deny_all, trust_mode=TrustMode.HIGH)
    call = ToolCall(actor="x", tool="some_obscure_tool", risk=RiskLevel.HIGH)
    with pytest.raises(ApprovalDenied):
        gate.run(call, _ctx("predev"), execute=lambda: "no")
