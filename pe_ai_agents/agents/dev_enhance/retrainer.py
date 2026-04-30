"""Retrainer -- drives hard + soft retrain of an existing model.

Two modes:
  - hard: full re-fit on the latest training window
  - soft: warm start / hyperparameter refresh only

The agent calls the ``ds`` Kedro pipeline with a retrain-specific config,
then logs the resulting run to MLflow. Promoting a model to Production
is a separate HIGH-risk action (``mlflow_promote``) the agent does NOT
attempt -- a human gate handles that explicitly.
"""

from __future__ import annotations

from typing import Iterable

from pe_ai_agents.models.context import ResolvedContext
from pe_ai_agents.models.risk import RiskLevel, ToolCall
from pe_ai_agents.runtime.agent_base import Agent
from pe_ai_agents.skills.approval_gate import ApprovalGate
from pe_ai_agents.skills.mlflow_tracker import MLflowTracker
from pe_ai_agents.skills.provenance import ProvenanceLedger
from pe_ai_agents.tools.kedro import FakeKedro


class Retrainer(Agent):
    name = "retrainer"

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        kedro: FakeKedro,
        mlflow: MLflowTracker,
        mode: str = "soft",  # "hard" | "soft"
    ) -> None:
        if mode not in ("hard", "soft"):
            raise ValueError(f"unknown retrain mode {mode!r}")
        self._mlflow = mlflow
        self._kedro = kedro
        self._mode = mode
        self._last_kedro_run_id: str | None = None
        super().__init__(
            gate=gate,
            ledger=ledger,
            tools={
                "kedro_run": self._tool_run,
                "kedro_poll": self._tool_poll,
                "mlflow_log": self._tool_mlflow_log,
            },
        )

    def _plan(self, ctx: ResolvedContext, request: str) -> Iterable[ToolCall]:
        yield ToolCall(
            actor=self.name,
            tool="kedro_run",
            args={
                "pipeline": "ds",
                "overrides": {
                    "brand": ctx.brand,
                    "indication": ctx.indication,
                    "env": ctx.env,
                    "mode": "retrain",
                    "retrain": self._mode,
                },
            },
            rationale=f"{self._mode} retrain on ds pipeline",
        )
        yield ToolCall(
            actor=self.name,
            tool="kedro_poll",
            risk=RiskLevel.LOW,
            rationale="check terminal state",
        )
        yield ToolCall(
            actor=self.name,
            tool="mlflow_log",
            args={"experiment": f"{ctx.brand}_{ctx.indication}_retrain_{self._mode}"},
            risk=RiskLevel.LOW,
            rationale="log retrain run + metrics to MLflow",
        )

    def _tool_run(self, *, pipeline: str, overrides: dict) -> dict:
        run = self._kedro.run(pipeline=pipeline, overrides=overrides)
        self._last_kedro_run_id = run.run_id
        return {"kedro_run_id": run.run_id, "state": run.state.value}

    def _tool_poll(self) -> dict:
        if self._last_kedro_run_id is None:
            return {"kedro_run_id": None, "state": "no_run"}
        run = self._kedro.poll(self._last_kedro_run_id)
        return {
            "kedro_run_id": run.run_id,
            "state": run.state.value,
            "failed_node": run.failed_node,
        }

    def _tool_mlflow_log(self, *, experiment: str) -> dict:
        run = self._mlflow.start_run(
            experiment=experiment,
            params={"retrain_mode": self._mode, "kedro_run_id": self._last_kedro_run_id},
        )
        # Stub metrics -- in real life pulled from the kedro run artifact catalog.
        self._mlflow.log_metrics(run.run_id, {"auc": 0.0, "calibration_error": 0.0})
        self._mlflow.end_run(run.run_id)
        return {"mlflow_run_id": run.run_id, "experiment": experiment, "stage": run.stage}
