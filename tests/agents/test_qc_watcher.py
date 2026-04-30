"""QC Watcher -- read-only QC sweep + alert emission."""

from __future__ import annotations

from pe_ai_agents.agents.ops.qc_watcher import QCWatcher
from pe_ai_agents.skills.alerts import Severity
from pe_ai_agents.tools.dqm import DQMFinding


def test_quiet_when_nothing_fails(
    gate_low_allow, ledger, alerts, dqm, pk, territory, workspace_ctx
):
    agent = QCWatcher(
        gate=gate_low_allow, ledger=ledger, alerts=alerts,
        dqm=dqm, pk=pk, territory=territory,
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    assert result.artifacts["alerts_emitted"] == 0
    assert alerts.read() == []


def test_dqm_warn_findings_become_alerts(
    gate_low_allow, ledger, alerts, dqm, pk, territory, workspace_ctx
):
    dqm.inject([
        DQMFinding(check="null_rate", table="events_x", severity="warn", detail="3.4%"),
        DQMFinding(check="row_count", table="events_x", severity="critical", detail="dropped 50%"),
        DQMFinding(check="distribution", table="events_x", severity="info", detail="ok"),
    ])
    agent = QCWatcher(
        gate=gate_low_allow, ledger=ledger, alerts=alerts,
        dqm=dqm, pk=pk, territory=territory,
    )
    result = agent.run(workspace_ctx, "")
    emitted = alerts.read()
    # info finding should be filtered out -- only warn + critical alerts.
    assert len(emitted) == 2
    severities = {a.severity for a in emitted}
    assert Severity.WARN in severities
    assert Severity.CRITICAL in severities
    assert result.artifacts["alerts_emitted"] == 2


def test_pk_failure_emits_critical(
    gate_low_allow, ledger, alerts, dqm, pk, territory, workspace_ctx
):
    pk.set_result("events_patient_journey_tremfya", ok=False)
    agent = QCWatcher(
        gate=gate_low_allow, ledger=ledger, alerts=alerts,
        dqm=dqm, pk=pk, territory=territory,
    )
    agent.run(workspace_ctx, "")
    emitted = alerts.read()
    assert len(emitted) == 1
    assert emitted[0].code == "pk.duplicates"
    assert emitted[0].severity == Severity.CRITICAL


def test_territory_few_failures_warns_many_failures_critical(
    gate_low_allow, ledger, alerts, dqm, pk, territory, workspace_ctx
):
    territory.fail(0, 1, 2, 3, 4, 5)  # 6 failures -> CRITICAL
    agent = QCWatcher(
        gate=gate_low_allow, ledger=ledger, alerts=alerts,
        dqm=dqm, pk=pk, territory=territory,
    )
    agent.run(workspace_ctx, "")
    emitted = alerts.read()
    assert len(emitted) == 1
    assert emitted[0].code == "territory_qc.fails"
    assert emitted[0].severity == Severity.CRITICAL
