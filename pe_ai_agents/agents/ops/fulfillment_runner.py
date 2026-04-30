"""Fulfillment Runner -- runs the fulfillment scoring leg of the pipeline.

In the current PE.AI codebase fulfillment + persistency are both served
by the ``ds`` / ``ds_insights`` Kedro pipeline with different config
bundles. This agent calls ``ds`` with the fulfillment override.
"""

from __future__ import annotations

from pe_ai_agents.agents.ops._kedro_runner import _KedroRunnerBase
from pe_ai_agents.models.context import ResolvedContext


class FulfillmentRunner(_KedroRunnerBase):
    name = "fulfillment_runner"
    pipeline_name = "ds"

    def _overrides(self, ctx: ResolvedContext) -> dict:
        base = super()._overrides(ctx)
        base["model"] = "fulfillment"
        base["fulfillment_window_days"] = ctx.fulfillment_window_days
        return base
