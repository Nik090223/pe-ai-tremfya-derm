"""Cohort/Feature/Model Builder + QC Reviewer (dev_build)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pe_ai_agents.agents.dev_build.cohort_builder import CohortBuilder
from pe_ai_agents.agents.dev_build.feature_builder import FeatureBuilder
from pe_ai_agents.agents.dev_build.model_builder import ModelBuilder
from pe_ai_agents.agents.dev_build.qc_reviewer import QCReviewer
from pe_ai_agents.skills.kpi_registry import KPIRegistry
from pe_ai_agents.skills.mlflow_tracker import MLflowTracker


REPO_KPI_DIR = Path(__file__).resolve().parents[2] / "conf" / "kpi_registry"


def test_cohort_builder_loads_per_subindication(
    gate_low_allow, ledger, journey, workspace_ctx
):
    agent = CohortBuilder(
        gate=gate_low_allow, ledger=ledger, journey=journey, anchor_event="referral",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    summary = result.artifacts["cohort_summarize"]
    assert summary["anchor_event"] == "referral"
    assert "total_patients" in summary


def test_feature_builder_produces_diff_and_proposal(
    gate_low_allow, ledger, conf_files, workspace_ctx
):
    agent = FeatureBuilder(
        gate=gate_low_allow, ledger=ledger, conf=conf_files,
        feature_id="months_since_first_referral",
        feature_yaml="months_since_first_referral:\n  source: events\n",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    draft = result.artifacts["feature_yaml_draft"]
    assert draft["feature_id"] == "months_since_first_referral"
    assert "months_since_first_referral" in draft["diff"]
    proposal = result.artifacts["kpi_register_proposal"]
    assert proposal["status"] == "proposed"


def test_model_builder_rejects_unknown_family(gate_low_allow, ledger, kedro):
    with pytest.raises(ValueError):
        ModelBuilder(
            gate=gate_low_allow, ledger=ledger, kedro=kedro,
            mlflow=MLflowTracker(), family="random_forest",
        )


def test_model_builder_runs_candidate_then_logs(gate_low_allow, ledger, kedro, workspace_ctx):
    mlflow = MLflowTracker()
    agent = ModelBuilder(
        gate=gate_low_allow, ledger=ledger, kedro=kedro,
        mlflow=mlflow, family="xgboost",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    runs = mlflow.list()
    assert len(runs) == 1
    assert runs[0].params["family"] == "xgboost"
    assert runs[0].experiment.endswith("candidate_xgboost")


def test_qc_reviewer_passes_when_metrics_in_band(gate_low_allow, ledger, workspace_ctx):
    agent = QCReviewer(
        gate=gate_low_allow, ledger=ledger,
        kpis=KPIRegistry(root=REPO_KPI_DIR),
        mlflow_run_id="mlflow-0001",
        candidate_metrics={
            "fulfillment_rate_84d": 0.65,
            "persistency_rate_180d": 0.74,
        },
    )
    result = agent.run(workspace_ctx, "")
    compare = result.artifacts["qc_compare"]
    assert compare["ok"]
    assert all(row["in_range"] for row in compare["rows"])


def test_qc_reviewer_fails_when_metric_out_of_band(gate_low_allow, ledger, workspace_ctx):
    agent = QCReviewer(
        gate=gate_low_allow, ledger=ledger,
        kpis=KPIRegistry(root=REPO_KPI_DIR),
        mlflow_run_id="mlflow-0001",
        candidate_metrics={
            "fulfillment_rate_84d": 0.30,  # below benchmark min 0.55
        },
    )
    result = agent.run(workspace_ctx, "")
    assert result.artifacts["qc_compare"]["ok"] is False


def test_qc_reviewer_handles_unknown_kpi(gate_low_allow, ledger, workspace_ctx):
    agent = QCReviewer(
        gate=gate_low_allow, ledger=ledger,
        kpis=KPIRegistry(root=REPO_KPI_DIR),
        mlflow_run_id="mlflow-0001",
        candidate_metrics={"made_up_kpi": 0.5},
    )
    result = agent.run(workspace_ctx, "")
    rows = result.artifacts["qc_compare"]["rows"]
    assert rows[0]["in_range"] is False
    assert rows[0]["benchmark"] is None
