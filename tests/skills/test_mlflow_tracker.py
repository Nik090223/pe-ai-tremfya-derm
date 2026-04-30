"""MLflow tracker stub -- run lifecycle + promotion."""

from __future__ import annotations

import pytest

from pe_ai_agents.skills.mlflow_tracker import MLflowTracker


def test_start_run_assigns_unique_ids() -> None:
    tracker = MLflowTracker()
    a = tracker.start_run(experiment="ds", params={"lr": 0.1})
    b = tracker.start_run(experiment="ds")
    assert a.run_id != b.run_id
    assert a.experiment == "ds"
    assert a.params == {"lr": 0.1}


def test_log_metrics_accumulates() -> None:
    tracker = MLflowTracker()
    run = tracker.start_run(experiment="ds")
    tracker.log_metrics(run.run_id, {"auc": 0.81})
    tracker.log_metrics(run.run_id, {"f1": 0.65})
    fetched = tracker.get(run.run_id)
    assert fetched.metrics == {"auc": 0.81, "f1": 0.65}


def test_end_run_sets_ended_at() -> None:
    tracker = MLflowTracker()
    run = tracker.start_run(experiment="ds")
    assert run.ended_at is None
    tracker.end_run(run.run_id)
    assert tracker.get(run.run_id).ended_at is not None


def test_promote_changes_stage() -> None:
    tracker = MLflowTracker()
    run = tracker.start_run(experiment="ds")
    tracker.promote(run.run_id, to_stage="Staging")
    assert tracker.get(run.run_id).stage == "Staging"
    tracker.promote(run.run_id, to_stage="Production")
    assert tracker.get(run.run_id).stage == "Production"


def test_promote_rejects_unknown_stage() -> None:
    tracker = MLflowTracker()
    run = tracker.start_run(experiment="ds")
    with pytest.raises(ValueError):
        tracker.promote(run.run_id, to_stage="Live")


def test_list_filters_by_experiment() -> None:
    tracker = MLflowTracker()
    tracker.start_run(experiment="ds")
    tracker.start_run(experiment="ds")
    tracker.start_run(experiment="cohort")
    assert len(tracker.list()) == 3
    assert len(tracker.list(experiment="ds")) == 2
    assert len(tracker.list(experiment="cohort")) == 1
