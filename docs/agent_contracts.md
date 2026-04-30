# Agent Contracts

One row per agent: role, tool table, risk policy entry points, and the
gate state-machine the operator should expect under `LOW` trust.

Risk column refers to the call's effective risk under
`approval_gate._POLICY` for the `predev` env unless flagged `(prod)`.

## Ops

### Fulfillment Runner (`fulfillment_runner`)

**Role.** Run fulfillment scoring leg of the pipeline.
**Underlying call.** `kedro.run(pipeline="ds", overrides={..., model="fulfillment", fulfillment_window_days})` then `poll`.

| Tool        | Risk           | Gate under LOW |
|-------------|----------------|----------------|
| kedro_list  | LOW            | silent         |
| kedro_run   | MEDIUM (HIGH in prod) | prompt  |
| kedro_poll  | LOW            | silent         |

### Persistency Runner (`persistency_runner`)

Same pipeline as Fulfillment Runner; overrides set `model="persistency"`.

### Account Prioritizer (`account_prioritizer`)

`pipeline="post_processing"`. Same plan shape as the runners. For
oncology repos override `pipeline_name="cross_onc"`.

### QC Watcher (`qc_watcher`)

**Always-on.** Read-only sweep that emits alerts.

| Tool             | Risk | Side-effect             |
|------------------|------|--------------------------|
| dqm_run_checks   | LOW  | warn/critical -> alert  |
| pk_check         | LOW  | failure -> CRITICAL alert |
| territory_qc_run | LOW  | >=5 fails -> CRITICAL    |

Override: `run()` augments `AgentResult` with `alerts_emitted`.

## Dev -- Enhance

### Retrainer (`retrainer`)

| Tool        | Risk   | Notes |
|-------------|--------|-------|
| kedro_run   | MEDIUM | hard / soft retrain on `ds` |
| kedro_poll  | LOW    |       |
| mlflow_log  | LOW    | params + stub metrics; does NOT promote |

Promotion (`mlflow_promote`) is a HIGH-risk action handled outside this agent.

### Tweaker (`tweaker`)

Drafts a config edit and routes through one of two PR tools:

| Target path                      | Tool                | Risk    |
|----------------------------------|---------------------|---------|
| `conf/base/...`                  | conf_draft_pr_base  | HIGH    |
| `conf/{brand}/...`               | conf_draft_pr_brand | MEDIUM  |

`conf_read` and `conf_diff` are LOW.

## Dev -- Build

### Cohort Builder (`cohort_builder`)

| Tool              | Risk |
|-------------------|------|
| journey_load      | LOW  |
| cohort_summarize  | LOW  |

Loads journey events for each `ctx.sub_indications`, summarizes anchored
patients per indication.

### Feature Builder (`feature_builder`)

| Tool                 | Risk   |
|----------------------|--------|
| conf_read            | LOW    |
| feature_yaml_draft   | MEDIUM |
| kpi_register_proposal| LOW    |

Always emits a `kpi_register_proposal` artifact for human review; never
mutates the KPI registry directly.

### Model Builder (`model_builder`)

Allowed families: `xgboost`, `cox`, `dml`, `s_learner`. Same tool table
as `Retrainer`. Promotion is out of scope.

### QC Reviewer (`qc_reviewer`)

| Tool        | Risk |
|-------------|------|
| kpi_lookup  | LOW  |
| qc_compare  | LOW  |

Pure read-only. Returns `ok=False` when any candidate metric falls
outside the matching KPI benchmark range. Does not auto-promote.

## Dev -- Ad-hoc

### Quick Analyst (`quick_analyst`)

| Tool          | Risk |
|---------------|------|
| journey_load  | LOW  |
| eda_summarize | LOW  |
| write_brief   | LOW  |

Writes `runs/<run_id>/quick_analysis.md`. No pipeline mutations, no
external sends.

## Risk policy quick reference

From `pe_ai_agents/skills/approval_gate.py::_POLICY`:

| Tool                      | predev/dev | prod  |
|---------------------------|------------|-------|
| kedro_list / poll         | LOW        | LOW   |
| kedro_run                 | MEDIUM     | HIGH  |
| argo_submit               | MEDIUM     | HIGH  |
| dep_push_to_mbox          | HIGH       | HIGH  |
| mlflow_promote            | HIGH       | HIGH  |
| conf_draft_pr_base        | HIGH       | HIGH  |
| conf_draft_pr_brand       | MEDIUM     | HIGH  |
| dqm_run_checks / pk_check | LOW        | LOW   |
| territory_qc_run          | LOW        | LOW   |
| journey_load / db_query   | LOW        | LOW   |

Anything not in `_POLICY` falls back to the call's declared `ToolCall.risk`.
