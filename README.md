# pe-ai-tremfya-derm

**Reference implementation** of the PE.AI agentic harness for one
brand-therapy-area: **Tremfya x Derm**, covering Plaque Psoriasis (PsO)
+ Psoriatic Arthritis (PsA), which the PE.AI codebase trains as **one
joint Insights model** (`tremfya_pso_psa_frm_pkl_file_*.pkl`,
`model_indications: [pso, psa]`).

The repo unit is **brand x jointly-trained model**. PsO and PsA are not
split into separate repos because they share one model artifact, one
conf tree, one feature set, and one Kedro pipeline -- splitting them
would create two near-identical repos with nothing meaningful isolated.

| Repo                  | Brand    | Therapy area                | Joint model       | Status     |
|-----------------------|----------|-----------------------------|-------------------|------------|
| `pe-ai-tremfya-derm`  | Tremfya  | Derm (PsO + PsA)            | insights model    | reference  |
| `pe-ai-tremfya-gi`    | Tremfya  | GI (UC + CD)                | FRM model         | live       |
| `pe-ai-erleada`       | Erleada  | Prostate (mCRPC/mCSPC/nmCRPC)| oncology model   | live       |
| `pe-ai-spravato-*`    | Spravato | TBD                         | -                 | stub       |

Boundaries are drawn from the upstream `conf/{brand}/data_science/*/parameters/data_science.yml::model_indications`:

- Tremfya `insights/`: `[pso, psa]`  -> Derm
- Tremfya `frm/`:      `[uc, cd]`    -> GI
- Erleada `frm/`:      mCRPC/mCSPC/nmCRPC -> Oncology

## Mental model

```
                                Tremfya Derm team
                                -----------------
   OPS workstream (run pipeline)        [O]
   DEV workstream (build / iterate)     [D]
```

Each team opens their workspace and calls agents directly. There is no router.

### Agents

**Ops** (3 user-invoked + 1 always-on)
- `Fulfillment Runner`  - run fulfillment scoring
- `Persistency Runner`  - run persistency scoring
- `Account Prioritizer` - aggregate scores + apply top-account framework
- `QC Watcher`          - continuous checks + alerts to the QC dashboard

**Dev**
- *Enhance*: `Retrainer`, `Tweaker`
- *Build*:   `Cohort Builder`, `Feature Builder`, `Model Builder`, `QC Reviewer`
- *Ad-hoc*:  `Quick Analyst`

### Skills (reusable, not user-facing)
`brand_context`, `kpi_registry`, `provenance`, `approval_gate`, `mlflow_tracker`, `alerts`

### Tools (thin adapters over the PE.AI codebase)
`kedro`, `argo`, `dqm`, `mlflow`, `db`, `journey`, `conf`, `email`

## Trust mode

Default: **LOW** for both `ops` and `dev`. Every mutating tool call prompts the
operator for approval; read-only tools run silently. Edit `conf/trust_mode.yml`
to dial up to `MEDIUM` or `HIGH` once the team has built confidence in the
agents.

## Quick start

```bash
pip install -e .[dev]
pytest

# Ops CLI (lists agents and runs them against local fakes)
python -m workspaces.ops.cli --list
python -m workspaces.ops.cli fulfillment_runner

# Dev CLI
python -m workspaces.dev.cli --list
```

## QC dashboard

```bash
# Local
docker build -t pe-ai-qc:dev qc_dashboard
docker run --rm -p 8000:8000 -v "$PWD/runs:/app/runs" pe-ai-qc:dev

# K8s (J&J cluster)
kubectl apply -f qc_dashboard/deploy/
```

## Cloning to a sibling brand-therapy-area

To create `pe-ai-tremfya-gi` (or any other sibling) from this repo:

1. `cp -r pe-ai-tremfya-derm pe-ai-tremfya-gi`
2. Edit `pe_ai_agents/skills/brand_context.py::BRAND_SPEC` -- set
   `indication="gi"`, `sub_indications=("uc", "cd")`. Keep
   `brand`/`product`/`data_source` if same brand.
3. Replace `conf/kpi_registry/*.yml` with KPIs for the GI joint model
   (different benchmarks).
4. Update `pyproject.toml::project.name` and the README sibling table.
5. For Account Prioritizer: if the new repo runs `cross_onc` instead of
   `post_processing` (e.g. Erleada), override `pipeline_name` on the
   `AccountPrioritizer` subclass in `pe_ai_agents/agents/ops/account_prioritizer.py`.
6. `pytest` -- the test suite catches most copy-paste mistakes.

After 2-3 sibling repos exist, extract the shared code into
`pe-ai-harness` as a versioned library (see `docs/replication.md`).

## Repo layout

```
pe_ai_agents/
  agents/      -- agents grouped by workstream/track
  skills/      -- reusable cross-agent capabilities
  tools/       -- thin adapters over the PE.AI codebase
  runtime/     -- agent base, trust mode, workspace loader
  models/      -- shared dataclasses
workspaces/
  ops/         -- CLI for the Ops team
  dev/         -- CLI for the Dev team
qc_dashboard/  -- FastAPI app, frontend, K8s manifests
conf/          -- KPI registry + trust_mode.yml
runs/          -- provenance ledgers (gitignored except sample)
tests/         -- pytest suites
docs/          -- design + diagrams
```
