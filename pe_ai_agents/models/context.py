"""Immutable domain models for workspace, brand context, and agent results."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Workstream(str, Enum):
    OPS = "ops"
    DEV = "dev"


class TrustMode(str, Enum):
    """Per-workstream HITL posture (set in conf/trust_mode.yml).

    LOW    -- gate every mutating tool call.
    MEDIUM -- gate only prod-namespace mutations, MBOX delivery, model
              promotions, and conf/base/* edits.
    HIGH   -- only gate the explicit risk=HIGH list.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ResolvedContext:
    """Brand-resolved context every agent receives at run time.

    Produced by the brand_context skill. Immutable once built.
    """

    brand: str               # "tremfya" | "erleada" | "spravato"
    indication: str          # therapy-area code: "derm" | "gi" | "oncology" | ...
    sub_indications: tuple[str, ...]  # ("pso", "psa") for derm; ("uc", "cd") for gi
    run_type: str            # matches conf/{brand}/run_type
    env: str                 # "predev" | "dev" | "prod"
    data_start: date
    data_end: date
    product: str             # mirrors conf/{brand}/data_engineering/globals.yml::product
    data_source: str         # "IQVIA" | "SHS" | ...
    fulfillment_window_days: int
    run_id: str

    def is_prod(self) -> bool:
        return self.env == "prod"


@dataclass(frozen=True)
class WorkspaceContext:
    """The (workstream, brand-context, trust-mode) bundle a workspace passes
    to every agent it invokes.
    """

    workstream: Workstream
    resolved: ResolvedContext
    trust: TrustMode

    @property
    def run_id(self) -> str:
        return self.resolved.run_id


@dataclass
class AgentResult:
    """Returned by every agent run. Includes both successful outputs and
    structured info on what was denied/skipped, for transparent reporting.
    """

    actor: str
    ok: bool
    summary: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    denied_calls: list[str] = field(default_factory=list)


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
