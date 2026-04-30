"""Ops Kedro-driven runners -- Fulfillment, Persistency, Account Prioritizer.

Same plan shape (list -> run -> poll), different pipeline + overrides.
"""

from __future__ import annotations

from pe_ai_agents.agents.ops.account_prioritizer import AccountPrioritizer
from pe_ai_agents.agents.ops.fulfillment_runner import FulfillmentRunner
from pe_ai_agents.agents.ops.persistency_runner import PersistencyRunner
from pe_ai_agents.models.context import WorkspaceContext


def _ws(workspace_ctx: WorkspaceContext) -> WorkspaceContext:
    return workspace_ctx


def test_fulfillment_runner_runs_ds_with_fulfillment_override(
    gate_low_allow, ledger, kedro, workspace_ctx
):
    agent = FulfillmentRunner(gate=gate_low_allow, ledger=ledger, kedro=kedro)
    result = agent.run(workspace_ctx, "")
    assert result.ok
    run_artifact = result.artifacts["kedro_run"]
    assert run_artifact["pipeline"] == "ds"
    assert run_artifact["state"] == "running"
    poll = result.artifacts["kedro_poll"]
    assert poll["state"] == "succeeded"


def test_persistency_runner_uses_ds_with_persistency_override(
    gate_low_allow, ledger, kedro, workspace_ctx
):
    agent = PersistencyRunner(gate=gate_low_allow, ledger=ledger, kedro=kedro)
    result = agent.run(workspace_ctx, "")
    assert result.artifacts["kedro_run"]["pipeline"] == "ds"


def test_account_prioritizer_uses_post_processing(
    gate_low_allow, ledger, kedro, workspace_ctx
):
    agent = AccountPrioritizer(gate=gate_low_allow, ledger=ledger, kedro=kedro)
    result = agent.run(workspace_ctx, "")
    assert result.artifacts["kedro_run"]["pipeline"] == "post_processing"


def test_runner_low_trust_denies_kedro_run(
    gate_low_deny, ledger, kedro, workspace_ctx
):
    agent = FulfillmentRunner(gate=gate_low_deny, ledger=ledger, kedro=kedro)
    result = agent.run(workspace_ctx, "")
    # kedro_list (LOW) succeeds, kedro_run (MEDIUM) is denied,
    # poll runs but reports "no_run" since run was blocked.
    assert "kedro_run" in result.denied_calls
    assert "kedro_list" in result.artifacts
    assert result.ok is False


def test_runner_records_provenance(gate_low_allow, ledger, kedro, workspace_ctx):
    agent = FulfillmentRunner(gate=gate_low_allow, ledger=ledger, kedro=kedro)
    agent.run(workspace_ctx, "")
    rows = ledger.read(workspace_ctx.resolved.run_id)
    actions = [r["action"] for r in rows]
    assert "dispatch" in actions
    assert "tool:kedro_list" in actions
    assert "tool:kedro_run" in actions
    assert "tool:kedro_poll" in actions
