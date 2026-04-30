"""Model Builder -- trains and evaluates a new model candidate.

Submits the ``ds`` Kedro pipeline in a candidate experiment configuration
(XGB / Cox / DML / S-Learner are toggled via overrides), then logs the
candidate run to MLflow. Promoting the candidate to Staging/Production
is a separate HIGH-risk action handled outside this agent.
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


class ModelBuilder(Agent):
    name = "model_builder"

    SUPPORTED_FAMILIES = ("xgboost", "cox", "dml", "s_learner")

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        ledger: ProvenanceLedger,
        kedro: FakeKedro,
        mlflow: MLflowTracker,
        family: str,
    ) -> None:
        if family not in self.SUPPORTED_FAMILIES:
            raise ValueError(
                f"unknown model family {family!r}; supported: {self.SUPPORTED_FAMILIES}"
            )
        self._kedro = kedro
        self._mlflow = mlflow
        self._family = family
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
                    "mode": "candidate",
                    "model_family": self._family,
                },
            },
            rationale=f"train {self._family} candidate",
        )
        yield ToolCall(
            actor=self.name,
            tool="kedro_poll",
            risk=RiskLevel.LOW,
        )
        yield ToolCall(
            actor=self.name,
            tool="mlflow_log",
            args={"experiment": f"{ctx.brand}_{ctx.indication}_candidate_{self._family}"},
            risk=RiskLevel.LOW,
        )

    def _tool_run(self, *, pipeline: str, overrides: dict) -> dict:
        run = self._kedro.run(pipeline=pipeline, overrides=overrides)
        self._last_kedro_run_id = run.run_id
        return {"kedro_run_id": run.run_id, "state": run.state.value}

    def _tool_poll(self) -> dict:
        if self._last_kedro_run_id is None:
            return {"kedro_run_id": None, "state": "no_run"}
        run = self._kedro.poll(self._last_kedro_run_id)
        return {"kedro_run_id": run.run_id, "state": run.state.value}

    def _tool_mlflow_log(self, *, experiment: str) -> dict:
        run = self._mlflow.start_run(
            experiment=experiment,
            params={"family": self._family, "kedro_run_id": self._last_kedro_run_id},
        )
        self._mlflow.log_metrics(run.run_id, {"auc": 0.0, "calibration_error": 0.0})
        self._mlflow.end_run(run.run_id)
        return {"mlflow_run_id": run.run_id, "experiment": experiment, "stage": run.stage}
