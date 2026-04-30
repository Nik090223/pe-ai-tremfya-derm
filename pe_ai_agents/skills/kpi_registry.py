"""KPI Registry -- versioned KPI definitions in ``conf/kpi_registry/*.yml``.

A KPI is the single source of truth for a metric: formula, source tables,
owner, brand applicability, and a benchmark range that the QC Reviewer
agent uses to decide whether new model output is plausible.

Schema (one YAML file per KPI, kebab-case filename matches ``kpi_id``):

    kpi_id: fulfillment_rate_84d
    name: 84-day fulfillment rate
    version: 2026-04-01
    owner: ops-team@jnj.example
    formula: filled_within_84d / total_referrals
    source_tables:
      - events_patient_journey_tremfya
    brands_applicable: [tremfya]
    benchmark:
      min: 0.55
      max: 0.78
    notes: ...

This skill is read-only at runtime. Adding a KPI is a HIGH-risk action
that goes through ``conf_draft_pr_base``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class KPINotFound(KeyError):
    """Raised when a KPI id is requested but not in the registry."""


@dataclass(frozen=True)
class KPIBenchmark:
    min: float
    max: float

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max


@dataclass(frozen=True)
class KPI:
    kpi_id: str
    name: str
    version: str
    owner: str
    formula: str
    source_tables: tuple[str, ...] = ()
    brands_applicable: tuple[str, ...] = ()
    benchmark: KPIBenchmark | None = None
    notes: str = ""

    def applies_to(self, brand: str) -> bool:
        return brand in self.brands_applicable


@dataclass
class KPIRegistry:
    """Read-only registry loaded from ``conf/kpi_registry/``."""

    root: Path
    _kpis: dict[str, KPI] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if not self.root.exists():
            return
        for path in sorted(self.root.glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self._kpis[data["kpi_id"]] = _kpi_from_dict(data)

    def get(self, kpi_id: str) -> KPI:
        if kpi_id not in self._kpis:
            raise KPINotFound(kpi_id)
        return self._kpis[kpi_id]

    def list(self, *, brand: str | None = None) -> list[KPI]:
        kpis = list(self._kpis.values())
        if brand:
            kpis = [k for k in kpis if k.applies_to(brand)]
        return kpis

    def __len__(self) -> int:
        return len(self._kpis)

    def __contains__(self, kpi_id: object) -> bool:
        return kpi_id in self._kpis


def _kpi_from_dict(data: dict[str, Any]) -> KPI:
    bench_dict = data.get("benchmark") or {}
    benchmark = (
        KPIBenchmark(min=float(bench_dict["min"]), max=float(bench_dict["max"]))
        if bench_dict
        else None
    )
    return KPI(
        kpi_id=data["kpi_id"],
        name=data["name"],
        version=str(data["version"]),
        owner=data["owner"],
        formula=data["formula"],
        source_tables=tuple(data.get("source_tables") or ()),
        brands_applicable=tuple(data.get("brands_applicable") or ()),
        benchmark=benchmark,
        notes=data.get("notes", ""),
    )
