"""KPI registry -- YAML loading, lookup, and benchmark semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from pe_ai_agents.skills.kpi_registry import KPIBenchmark, KPINotFound, KPIRegistry


REPO_KPI_DIR = Path(__file__).resolve().parents[2] / "conf" / "kpi_registry"


def test_loads_repo_sample_kpis() -> None:
    reg = KPIRegistry(root=REPO_KPI_DIR)
    assert "fulfillment_rate_84d" in reg
    assert "persistency_rate_180d" in reg
    assert len(reg) == 2


def test_get_returns_full_kpi() -> None:
    reg = KPIRegistry(root=REPO_KPI_DIR)
    kpi = reg.get("fulfillment_rate_84d")
    assert kpi.name == "84-day fulfillment rate"
    assert kpi.owner == "ops-team@jnj.example"
    assert kpi.formula == "filled_within_84d / total_referrals"
    assert kpi.brands_applicable == ("tremfya",)
    assert kpi.benchmark == KPIBenchmark(min=0.55, max=0.78)


def test_get_unknown_raises() -> None:
    reg = KPIRegistry(root=REPO_KPI_DIR)
    with pytest.raises(KPINotFound):
        reg.get("nonexistent_kpi")


def test_list_filters_by_brand() -> None:
    reg = KPIRegistry(root=REPO_KPI_DIR)
    assert {k.kpi_id for k in reg.list(brand="tremfya")} == {
        "fulfillment_rate_84d",
        "persistency_rate_180d",
    }
    assert reg.list(brand="erleada") == []


def test_benchmark_contains() -> None:
    bench = KPIBenchmark(min=0.5, max=0.8)
    assert bench.contains(0.5)
    assert bench.contains(0.8)
    assert bench.contains(0.65)
    assert not bench.contains(0.49)
    assert not bench.contains(0.81)


def test_applies_to() -> None:
    reg = KPIRegistry(root=REPO_KPI_DIR)
    kpi = reg.get("fulfillment_rate_84d")
    assert kpi.applies_to("tremfya")
    assert not kpi.applies_to("erleada")


def test_missing_root_returns_empty(tmp_path: Path) -> None:
    reg = KPIRegistry(root=tmp_path / "no_such_dir")
    assert len(reg) == 0
    assert reg.list() == []
