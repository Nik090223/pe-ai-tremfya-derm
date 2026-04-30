"""Quick Analyst -- ad-hoc EDA + markdown brief."""

from __future__ import annotations

from pathlib import Path

from pe_ai_agents.agents.dev_adhoc.quick_analyst import QuickAnalyst


def test_quick_analyst_writes_markdown_brief(
    gate_low_allow, ledger, journey, workspace_ctx, runs_dir: Path
):
    agent = QuickAnalyst(
        gate=gate_low_allow, ledger=ledger, journey=journey,
        runs_dir=runs_dir, question="What does fulfillment look like for PsA?",
    )
    result = agent.run(workspace_ctx, "")
    assert result.ok
    brief = result.artifacts["write_brief"]
    out_path = Path(brief["path"])
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "# Quick Analysis" in text
    assert "Event-type counts" in text
    assert workspace_ctx.resolved.run_id in text


def test_quick_analyst_summarizes_events(
    gate_low_allow, ledger, journey, workspace_ctx, runs_dir: Path
):
    agent = QuickAnalyst(
        gate=gate_low_allow, ledger=ledger, journey=journey,
        runs_dir=runs_dir,
    )
    result = agent.run(workspace_ctx, "")
    summary = result.artifacts["eda_summarize"]
    assert summary["patients"] > 0
    assert summary["avg_events_per_patient"] > 0
    assert set(summary["event_counts"].keys()).issubset(set(journey.EVENT_TYPES))
