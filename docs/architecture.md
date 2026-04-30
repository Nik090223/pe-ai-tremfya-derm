# PE.AI Agentic Harness -- Architecture (Tremfya Derm)

This document describes how the harness fits over the existing PE.AI
codebase. Read it before adding agents, tools, or skills.

## 1. Why this shape

The PE.AI team is organised on two stable axes:

- **Workstream**: Ops (run the pipeline) vs Dev (enhance / build / ad-hoc).
- **Brand-indication**: Tremfya Derm (PsO+PsA), Tremfya GI, Oncology, Spravato (stub).

Each team already knows which workstream and brand they belong to, so a
router/conductor adds no value. The harness instead exposes a pair of
workspaces -- Ops and Dev -- that the team uses directly. Each
brand-indication ships as its own Git repo.

## 2. Layers

```
+-----------------------+   user-facing CLI surfaces (Ops / Dev)
|     workspaces/       |
+-----------------------+
            |
            v
+-----------------------+   plan -> gate -> execute -> record
|   pe_ai_agents/agents |
+-----------------------+
            |
            v
+-----------------------+   reusable cross-agent capabilities
|   pe_ai_agents/skills |   brand_context, kpi_registry, provenance,
+-----------------------+   approval_gate, mlflow_tracker, alerts
            |
            v
+-----------------------+   thin adapters over PE.AI code; each tool
|   pe_ai_agents/tools  |   has a Fake* for tests / local demos
+-----------------------+
            |
            v
+-----------------------+   src/spc/pipeline_registry.py,
|   PE.AI codebase      |   master_argo_workflow/, dqm_wrapper.py,
+-----------------------+   mlflow_utils.py, ...
```

The `runtime/` package wires agents to the gate + ledger and provides
the Workspace bootstrap. `models/` holds shared dataclasses.

## 3. Plan -> gate -> execute -> record loop

Every agent inherits from `pe_ai_agents.runtime.agent_base.Agent`:

1. `_plan(ctx, request)` yields an ordered sequence of `ToolCall`s.
2. For each call, `ApprovalGate.run` decides whether the call needs a
   human, runs it if approved, returns `(result, gate_status)`.
3. The agent records dispatch + each tool call to
   `runs/<run_id>/provenance.jsonl` -- input/output hashes, gate status,
   workstream, brand, env.
4. Denied calls are recorded as `gate_status="denied"` and skipped; the
   agent still completes and reports them in `AgentResult.denied_calls`.

The deterministic Python `_plan` is the LLM extension point. A Claude
Agent SDK loop that emits `ToolCall` objects can drop in here; nothing
else changes.

## 4. Trust modes

`conf/trust_mode.yml` per repo:

```yaml
ops: LOW
dev: LOW
```

| Trust  | Read-only tools | Mutations (predev/dev) | HIGH-risk / prod mutations |
|--------|----------------|------------------------|----------------------------|
| LOW    | silent         | gate                   | gate                       |
| MEDIUM | silent         | silent                 | gate                       |
| HIGH   | silent         | silent                 | gate (HIGH only)           |

Risk per `(tool, env)` is fixed in
`pe_ai_agents/skills/approval_gate.py::_POLICY`. `ToolCall.risk` can
upgrade a call to HIGH on the fly; it cannot downgrade the policy.

## 5. KPI registry

Versioned YAML under `conf/kpi_registry/`. One file per KPI; the
filename matches `kpi_id`. The registry is read-only at runtime --
adding a KPI is a HIGH-risk action that goes through
`conf_draft_pr_base`. `QC Reviewer` uses benchmark ranges to decide
whether candidate models pass to Ops.

## 6. Provenance + alerts

- `runs/<run_id>/provenance.jsonl` -- one JSON object per line, append-only.
- `runs/qc_state.json` -- rolling alert feed the dashboard reads.
- Both are written under a shared `ReadWriteMany` PVC so the dashboard
  pod and agent jobs see the same files in K8s.

## 7. QC dashboard

FastAPI app under `qc_dashboard/`. Reads the provenance + alert files;
never writes. K8s manifests in `qc_dashboard/deploy/` (Deployment,
Service, Ingress with `oauth2-proxy` placeholders, ConfigMap,
ServiceAccount + Role, PVC).

## 8. Replication

`pe-ai-tremfya-gi`, `pe-ai-oncology`, `pe-ai-spravato` reuse this layout
1:1. The brand-specific surface lives in:

- `pe_ai_agents/skills/brand_context.py::BRAND_SPEC`
- `conf/kpi_registry/`
- `pe_ai_agents/agents/ops/account_prioritizer.py::pipeline_name`
  (e.g. `cross_onc` for oncology)

For Spravato the harness ships but `tools/kedro.py` raises
`PipelineNotConfigured` until brand configs land.

## 9. Where to add things

| Want to add ... | Put it in ... |
|---|---|
| A new mutation that any agent can perform | `tools/<adapter>.py` + entry in `_POLICY` |
| Something multiple agents need to share | `skills/` |
| A new role for the team | `agents/<workstream_track>/` |
| A new brand-indication | new repo, copy this one, edit BRAND_SPEC + KPIs |
