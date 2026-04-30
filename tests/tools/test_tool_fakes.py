"""Contract tests for the harness tool adapters (in-memory fakes).

These pin the shape of each tool the agents call so a real adapter that
ships later can be swapped in safely.
"""

from __future__ import annotations

import pytest

from pe_ai_agents.tools.argo import ArgoState, FakeArgo
from pe_ai_agents.tools.conf import FakeConf
from pe_ai_agents.tools.db import FakeDB
from pe_ai_agents.tools.dqm import (
    DQMFinding,
    FakeDQM,
    FakePrimaryKeyChecker,
    FakeTerritoryQC,
)
from pe_ai_agents.tools.email import FakeEmailNotifier
from pe_ai_agents.tools.journey import FakeJourneyLog
from pe_ai_agents.tools.kedro import FakeKedro, KedroState, PIPELINE_CATALOG, PipelineNotConfigured


# --- Kedro ----------------------------------------------------------------

def test_kedro_lists_canonical_pipelines() -> None:
    k = FakeKedro()
    assert "ds" in k.list_pipelines()
    assert "post_processing" in k.list_pipelines()
    assert tuple(k.list_pipelines()) == PIPELINE_CATALOG


def test_kedro_run_then_poll_succeeds() -> None:
    k = FakeKedro()
    run = k.run(pipeline="ds", overrides={"x": 1})
    assert run.state == KedroState.RUNNING
    polled = k.poll(run.run_id)
    assert polled.state == KedroState.SUCCEEDED


def test_kedro_run_can_be_forced_to_fail() -> None:
    k = FakeKedro(fail_pipelines=("ds",))
    run = k.run(pipeline="ds")
    polled = k.poll(run.run_id)
    assert polled.state == KedroState.FAILED
    assert polled.failed_node and "ds" in polled.failed_node


def test_kedro_unknown_pipeline_raises() -> None:
    k = FakeKedro()
    with pytest.raises(PipelineNotConfigured):
        k.run(pipeline="not_a_real_pipeline")


# --- Argo -----------------------------------------------------------------

def test_argo_submit_poll_succeeds() -> None:
    a = FakeArgo()
    run = a.submit(workflow_template="dag-tremfya")
    assert run.state == ArgoState.RUNNING
    polled = a.poll(run.run_id)
    assert polled.state == ArgoState.SUCCEEDED


def test_argo_failed_can_retry() -> None:
    a = FakeArgo(fail_templates=("flaky",))
    run = a.submit(workflow_template="flaky")
    a.poll(run.run_id)
    assert a._runs[run.run_id].state == ArgoState.FAILED
    retried = a.retry(run.run_id)
    assert retried.state == ArgoState.RUNNING
    assert retried.failed_node is None


# --- DQM / PK / Territory ------------------------------------------------

def test_dqm_inject_consume_once() -> None:
    d = FakeDQM()
    d.inject([DQMFinding(check="x", table="t", severity="warn", detail="d")])
    assert len(d.run_checks(brand="tremfya", env="predev")) == 1
    assert d.run_checks(brand="tremfya", env="predev") == []


def test_pk_default_ok() -> None:
    p = FakePrimaryKeyChecker()
    assert p.check(table="any")["ok"]
    p.set_result("bad", ok=False)
    assert p.check(table="bad")["ok"] is False


def test_territory_runs_27_checks() -> None:
    t = FakeTerritoryQC()
    out = t.run(brand="tremfya")
    assert out["passed"] == FakeTerritoryQC.NUM_CHECKS
    assert out["failed"] == 0
    t.fail(0, 5)
    out2 = t.run(brand="tremfya")
    assert out2["failed"] == 2


# --- Conf -----------------------------------------------------------------

def test_conf_read_returns_empty_for_missing_path() -> None:
    c = FakeConf()
    assert c.read("does/not/exist.yml") == ""


def test_conf_diff_and_draft_pr() -> None:
    c = FakeConf(files={"conf/x.yml": "a: 1\n"})
    d = c.diff("conf/x.yml", "a: 2\n")
    assert "-a: 1" in d
    assert "+a: 2" in d
    draft = c.draft_pr(path="conf/x.yml", proposed="a: 2\n")
    assert draft.original == "a: 1\n"
    assert draft.proposed == "a: 2\n"
    assert c.drafts == [draft]


# --- DB / Journey / Email ------------------------------------------------

def test_db_returns_registered_rows() -> None:
    db = FakeDB()
    db.register("select 1", [{"x": 1}])
    assert db.query(sql="  select   1  ") == [{"x": 1}]
    assert db.query(sql="select 2") == []


def test_journey_is_deterministic() -> None:
    j1 = FakeJourneyLog(n_patients=10, seed=42)
    j2 = FakeJourneyLog(n_patients=10, seed=42)
    assert [(e.patient_id, e.event_type) for e in j1.load(brand="tremfya", indication="pso")] == \
           [(e.patient_id, e.event_type) for e in j2.load(brand="tremfya", indication="pso")]


def test_journey_event_types_are_in_catalog() -> None:
    j = FakeJourneyLog(n_patients=5, seed=1)
    events = j.load(brand="tremfya", indication="psa")
    assert all(e.event_type in FakeJourneyLog.EVENT_TYPES for e in events)
    assert all(e.indication == "psa" for e in events)


def test_email_records_calls() -> None:
    e = FakeEmailNotifier()
    e("subj", "body")
    e("subj2", "body2")
    assert [r.subject for r in e.sent] == ["subj", "subj2"]
