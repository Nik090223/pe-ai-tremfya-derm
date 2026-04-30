"""Ops workspace CLI -- the entry point the Ops team uses.

  pe-ai-ops --list
  pe-ai-ops fulfillment_runner [--env predev]
  pe-ai-ops persistency_runner [--env predev]
  pe-ai-ops account_prioritizer [--env predev]
  pe-ai-ops qc_watcher [--env predev]

By default this runs against the in-memory Fake* tools so it works on a
laptop with no PE.AI codebase / Argo cluster on disk. Swap the bootstrap
in ``_build_workspace`` for the real adapters when running in K8s.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pe_ai_agents.agents.ops import (
    AccountPrioritizer,
    FulfillmentRunner,
    PersistencyRunner,
    QCWatcher,
)
from pe_ai_agents.models.context import Workstream
from pe_ai_agents.runtime.workspace import Workspace, stdin_approver
from pe_ai_agents.tools import (
    FakeDQM,
    FakeKedro,
    FakePrimaryKeyChecker,
    FakeTerritoryQC,
)


def _build_workspace(env: str, repo_root: Path) -> Workspace:
    ws = Workspace(
        workstream=Workstream.OPS,
        repo_root=repo_root,
        env=env,
        approver=stdin_approver,
    )
    kedro = FakeKedro()
    dqm = FakeDQM()
    pk = FakePrimaryKeyChecker()
    territory = FakeTerritoryQC()

    ws.register_many(
        [
            FulfillmentRunner(gate=ws.gate, ledger=ws.ledger, kedro=kedro),
            PersistencyRunner(gate=ws.gate, ledger=ws.ledger, kedro=kedro),
            AccountPrioritizer(gate=ws.gate, ledger=ws.ledger, kedro=kedro),
            QCWatcher(
                gate=ws.gate,
                ledger=ws.ledger,
                alerts=ws.alerts,
                dqm=dqm,
                pk=pk,
                territory=territory,
            ),
        ]
    )
    return ws


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pe-ai-ops")
    parser.add_argument("agent", nargs="?", help="agent to invoke")
    parser.add_argument("--list", action="store_true", help="list registered agents")
    parser.add_argument("--env", default="predev", choices=("predev", "dev", "prod"))
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent.parent),
        help="repo root (defaults to this repo)",
    )
    parser.add_argument("--request", default="", help="optional free-text request")
    args = parser.parse_args(argv)

    ws = _build_workspace(env=args.env, repo_root=Path(args.repo_root))

    if args.list or not args.agent:
        print("Ops workspace -- registered agents:")
        for n in ws.list_agents():
            print(f"  - {n}")
        print(f"\nbrand={ws.context.resolved.brand}-{ws.context.resolved.indication}  "
              f"env={ws.context.resolved.env}  trust={ws.trust.value}")
        return 0

    result = ws.invoke(args.agent, args.request)
    print(f"\n[{result.actor}] ok={result.ok}")
    print(f"  summary: {result.summary}")
    if result.denied_calls:
        print(f"  denied: {', '.join(result.denied_calls)}")
    print(f"  run_id: {ws.context.resolved.run_id}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
