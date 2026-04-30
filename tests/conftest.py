"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from pe_ai_agents.models.context import (
    ResolvedContext,
    TrustMode,
    WorkspaceContext,
    Workstream,
    new_run_id,
)
from pe_ai_agents.models.risk import ToolCall
from pe_ai_agents.skills.alerts import AlertSink
from pe_ai_agents.skills.approval_gate import ApprovalGate, allow_all, deny_all
from pe_ai_agents.skills.brand_context import resolve as resolve_brand
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools import (
    FakeArgo,
    FakeConf,
    FakeDB,
    FakeDQM,
    FakeJourneyLog,
    FakeKedro,
    FakePrimaryKeyChecker,
    FakeTerritoryQC,
)


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runs"
    d.mkdir()
    return d


@pytest.fixture
def ledger(runs_dir: Path) -> ProvenanceLedger:
    return ProvenanceLedger(runs_dir=runs_dir)


@pytest.fixture
def alerts(runs_dir: Path) -> AlertSink:
    return AlertSink(state_path=runs_dir / "qc_state.json")


@pytest.fixture
def gate_low_allow() -> ApprovalGate:
    """LOW trust + always-approve human -- exercise the prompt path."""
    return ApprovalGate(approver=allow_all, trust_mode=TrustMode.LOW)


@pytest.fixture
def gate_low_deny() -> ApprovalGate:
    """LOW trust + always-deny -- exercise the denial path."""
    return ApprovalGate(approver=deny_all, trust_mode=TrustMode.LOW)


@pytest.fixture
def gate_high_allow() -> ApprovalGate:
    """HIGH trust -- only HIGH risks gate; everything else autonomous."""
    return ApprovalGate(approver=allow_all, trust_mode=TrustMode.HIGH)


@pytest.fixture
def resolved() -> ResolvedContext:
    return resolve_brand(env="predev", run_id=new_run_id("test"))


@pytest.fixture
def workspace_ctx(resolved: ResolvedContext) -> WorkspaceContext:
    return WorkspaceContext(workstream=Workstream.OPS, resolved=resolved, trust=TrustMode.LOW)


# Tool fakes
@pytest.fixture
def kedro() -> FakeKedro:
    return FakeKedro()


@pytest.fixture
def argo() -> FakeArgo:
    return FakeArgo()


@pytest.fixture
def dqm() -> FakeDQM:
    return FakeDQM()


@pytest.fixture
def pk() -> FakePrimaryKeyChecker:
    return FakePrimaryKeyChecker()


@pytest.fixture
def territory() -> FakeTerritoryQC:
    return FakeTerritoryQC()


@pytest.fixture
def db() -> FakeDB:
    return FakeDB()


@pytest.fixture
def journey() -> FakeJourneyLog:
    return FakeJourneyLog(n_patients=50, seed=11)


@pytest.fixture
def conf_files() -> FakeConf:
    return FakeConf(
        files={
            "conf/tremfya/data_engineering/parameters.yml": "features: []\n",
            "conf/base/parameters.yml": "shared: {}\n",
        }
    )
