"""Thin adapters over the PE.AI codebase.

Each adapter exposes a small set of functions agents call. Defaults are
in-memory ``Fake*`` implementations so tests and demos run without
infrastructure. Real adapters subclass / replace the fakes in the
workspace bootstrap when running against a live cluster.
"""

from pe_ai_agents.tools.argo import ArgoRun, ArgoState, FakeArgo
from pe_ai_agents.tools.conf import ConfDraft, FakeConf
from pe_ai_agents.tools.db import FakeDB
from pe_ai_agents.tools.dqm import (
    DQMFinding,
    FakeDQM,
    FakePrimaryKeyChecker,
    FakeTerritoryQC,
)
from pe_ai_agents.tools.email import EmailRecord, FakeEmailNotifier
from pe_ai_agents.tools.journey import FakeJourneyLog, JourneyEvent
from pe_ai_agents.tools.kedro import (
    FakeKedro,
    KedroRun,
    KedroState,
    PIPELINE_CATALOG,
    PipelineNotConfigured,
)

__all__ = [
    "ArgoRun",
    "ArgoState",
    "ConfDraft",
    "DQMFinding",
    "EmailRecord",
    "FakeArgo",
    "FakeConf",
    "FakeDB",
    "FakeDQM",
    "FakeEmailNotifier",
    "FakeJourneyLog",
    "FakeKedro",
    "FakePrimaryKeyChecker",
    "FakeTerritoryQC",
    "JourneyEvent",
    "KedroRun",
    "KedroState",
    "PIPELINE_CATALOG",
    "PipelineNotConfigured",
]
