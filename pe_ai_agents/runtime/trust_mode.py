"""Loads ``conf/trust_mode.yml`` -- per-workstream HITL posture.

Format:

    ops:  LOW    # gate every mutation
    dev:  LOW

The file is mandatory; missing values default to LOW (most paranoid).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from pe_ai_agents.models.context import TrustMode, Workstream

DEFAULT_PATH = Path("conf/trust_mode.yml")


def load(path: Path | str | None = None) -> dict[Workstream, TrustMode]:
    """Return ``{Workstream.OPS: TrustMode.X, Workstream.DEV: TrustMode.Y}``."""
    p = Path(path) if path is not None else DEFAULT_PATH
    if not p.exists():
        return {ws: TrustMode.LOW for ws in Workstream}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[Workstream, TrustMode] = {}
    for ws in Workstream:
        value = str(raw.get(ws.value, "LOW")).upper()
        out[ws] = TrustMode(value.lower())
    return out


def get(workstream: Workstream, path: Path | str | None = None) -> TrustMode:
    return load(path).get(workstream, TrustMode.LOW)
