"""Persistency Runner -- runs the persistency scoring leg of the pipeline.

Same Kedro pipeline as the fulfillment runner (``ds``), called with the
persistency model bundle.
"""

from __future__ import annotations

from pe_ai_agents.agents.ops._kedro_runner import _KedroRunnerBase
from pe_ai_agents.models.context import ResolvedContext


class PersistencyRunner(_KedroRunnerBase):
    name = "persistency_runner"
    pipeline_name = "ds"

    def _overrides(self, ctx: ResolvedContext) -> dict:
        base = super()._overrides(ctx)
        base["model"] = "persistency"
        return base
