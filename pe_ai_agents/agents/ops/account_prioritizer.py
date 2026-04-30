"""Account Prioritizer -- aggregates patient scores and applies the
top-account prioritization framework.

Calls the ``post_processing`` Kedro pipeline. For Oncology repos the
analogous agent calls ``cross_onc`` instead; the shared base makes that
a one-line change.
"""

from __future__ import annotations

from pe_ai_agents.agents.ops._kedro_runner import _KedroRunnerBase


class AccountPrioritizer(_KedroRunnerBase):
    name = "account_prioritizer"
    pipeline_name = "post_processing"
