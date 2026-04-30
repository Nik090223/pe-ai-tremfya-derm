"""Retrainer + Tweaker (dev_enhance)."""

from __future__ import annotations

import pytest

from pe_ai_agents.agents.dev_enhance.retrainer import Retrainer
from pe_ai_agents.agents.dev_enhance.tweaker import Tweaker
from pe_ai_agents.skills.mlflow_tracker import MLflowTracker


def test_retrainer_rejects_unknown_mode(gate_low_allow, ledger, kedro):
    with pytest.raises(ValueError):
        Retrainer(
            gate=gate_low_allow, ledger=ledger, kedro=kedro,
            mlflow=MLflowTracker(), mode="full",
        )


def test_retrainer_runs_ds_then_logs_to_mlflow(gate_low_allow, ledger, kedro, workspace_ctx):
    mlflow = MLflowTracker()
    agent = Retrainer(
        gate=gate_low_allow, ledger=ledger, kedro=kedro,
        mlflow=mlflow, mode="hard",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    assert "mlflow_log" in result.artifacts
    runs = mlflow.list()
    assert len(runs) == 1
    assert runs[0].params["retrain_mode"] == "hard"
    assert runs[0].ended_at is not None


def test_retrainer_low_trust_denies_kedro_run(gate_low_deny, ledger, kedro, workspace_ctx):
    agent = Retrainer(
        gate=gate_low_deny, ledger=ledger, kedro=kedro,
        mlflow=MLflowTracker(), mode="soft",
    )
    result = agent.run(workspace_ctx, "")
    assert "kedro_run" in result.denied_calls


def test_tweaker_brand_path_uses_brand_gate(gate_low_allow, ledger, conf_files, workspace_ctx):
    agent = Tweaker(
        gate=gate_low_allow, ledger=ledger, conf=conf_files,
        target_path="conf/tremfya/data_engineering/parameters.yml",
        proposed_yaml="features:\n  - new_feature\n",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    assert result.artifacts["conf_draft_pr_brand"]["scope"] == "brand"
    assert "conf_draft_pr_base" not in result.artifacts


def test_tweaker_base_path_routes_through_high_risk_tool(
    gate_low_allow, ledger, conf_files, workspace_ctx
):
    agent = Tweaker(
        gate=gate_low_allow, ledger=ledger, conf=conf_files,
        target_path="conf/base/parameters.yml",
        proposed_yaml="shared:\n  thing: 1\n",
    )
    result = agent.run(workspace_ctx, "")
    assert "conf_draft_pr_base" in result.artifacts
    assert result.artifacts["conf_draft_pr_base"]["scope"] == "base"


def test_tweaker_base_edit_blocked_when_human_denies(
    gate_low_deny, ledger, conf_files, workspace_ctx
):
    agent = Tweaker(
        gate=gate_low_deny, ledger=ledger, conf=conf_files,
        target_path="conf/base/parameters.yml",
        proposed_yaml="shared: {}\n",
    )
    result = agent.run(workspace_ctx, "")
    assert "conf_draft_pr_base" in result.denied_calls
