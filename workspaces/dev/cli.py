"""Dev workspace CLI -- the entry point the Dev team uses.

  pe-ai-dev --list
  pe-ai-dev retrainer --mode soft|hard
  pe-ai-dev tweaker --target conf/... --proposed-file path.yml
  pe-ai-dev cohort_builder
  pe-ai-dev feature_builder --feature-id X --yaml-file path.yml
  pe-ai-dev model_builder --family xgboost|cox|dml|s_learner
  pe-ai-dev qc_reviewer --mlflow-run-id MLF --metrics auc=0.81,...
  pe-ai-dev quick_analyst --question "..."

Default bootstrap uses the in-memory Fake* tools. Swap real adapters in
``_build_workspace`` for production.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pe_ai_agents.agents.dev_adhoc import QuickAnalyst
from pe_ai_agents.agents.dev_build import (
    CohortBuilder,
    FeatureBuilder,
    ModelBuilder,
    QCReviewer,
)
from pe_ai_agents.agents.dev_enhance import Retrainer, Tweaker
from pe_ai_agents.models.context import Workstream
from pe_ai_agents.runtime.workspace import Workspace, stdin_approver
from pe_ai_agents.tools import FakeConf, FakeJourneyLog, FakeKedro


def _parse_metrics(spec: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if not spec:
        return out
    for chunk in spec.split(","):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        out[k.strip()] = float(v)
    return out


def _build_workspace(args, repo_root: Path) -> tuple[Workspace, dict[str, str]]:
    """Build a Workspace, registering the agents the user might invoke.

    Returns the workspace plus a small {agent_name -> human label} map for
    the --list output.
    """
    ws = Workspace(
        workstream=Workstream.DEV,
        repo_root=repo_root,
        env=args.env,
        approver=stdin_approver,
    )

    kedro = FakeKedro()
    journey = FakeJourneyLog()
    conf = FakeConf({
        "conf/tremfya/data_engineering/parameters.yml": "features: []\n",
    })

    # Register every agent in this workstream so --list shows the full menu.
    ws.register(Retrainer(gate=ws.gate, ledger=ws.ledger, kedro=kedro,
                          mlflow=ws.mlflow, mode=args.mode))
    ws.register(Tweaker(gate=ws.gate, ledger=ws.ledger, conf=conf,
                        target_path=args.target,
                        proposed_yaml=_read_or_inline(args.proposed_file, args.proposed)))
    ws.register(CohortBuilder(gate=ws.gate, ledger=ws.ledger, journey=journey))
    ws.register(FeatureBuilder(gate=ws.gate, ledger=ws.ledger, conf=conf,
                               feature_id=args.feature_id,
                               feature_yaml=_read_or_inline(args.yaml_file, args.feature_yaml)))
    ws.register(ModelBuilder(gate=ws.gate, ledger=ws.ledger, kedro=kedro,
                             mlflow=ws.mlflow, family=args.family))
    ws.register(QCReviewer(gate=ws.gate, ledger=ws.ledger, kpis=ws.kpis,
                           mlflow_run_id=args.mlflow_run_id,
                           candidate_metrics=_parse_metrics(args.metrics)))
    ws.register(QuickAnalyst(gate=ws.gate, ledger=ws.ledger, journey=journey,
                             runs_dir=repo_root / "runs",
                             question=args.question))
    return ws, {n: n for n in ws.list_agents()}


def _read_or_inline(file_path: str | None, inline: str) -> str:
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    return inline or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pe-ai-dev")
    parser.add_argument("agent", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--env", default="predev", choices=("predev", "dev", "prod"))
    parser.add_argument("--repo-root",
                        default=str(Path(__file__).resolve().parent.parent.parent))
    # Per-agent options. All optional so --list works with no extras.
    parser.add_argument("--mode", default="soft", choices=("soft", "hard"))
    parser.add_argument("--target", default="conf/tremfya/data_engineering/parameters.yml")
    parser.add_argument("--proposed", default="")
    parser.add_argument("--proposed-file", default=None)
    parser.add_argument("--feature-id", default="ft_example_28d")
    parser.add_argument("--feature-yaml", default="")
    parser.add_argument("--yaml-file", default=None)
    parser.add_argument("--family", default="xgboost",
                        choices=("xgboost", "cox", "dml", "s_learner"))
    parser.add_argument("--mlflow-run-id", default="mlflow-0001")
    parser.add_argument("--metrics", default="")
    parser.add_argument("--question", default="")
    parser.add_argument("--request", default="")
    args = parser.parse_args(argv)

    ws, _ = _build_workspace(args, Path(args.repo_root))

    if args.list or not args.agent:
        print("Dev workspace -- registered agents:")
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
