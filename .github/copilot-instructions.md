# Copilot instructions for pe-ai-tremfya-derm

This repo is the Tremfya x Derm (PsO + PsA) brand-indication slice of
the PE.AI agentic harness. When suggesting code, follow these rules.

## Architecture rules (do not violate)

1. **Plan -> gate -> execute -> record loop.** Every agent inherits
   from `pe_ai_agents.runtime.agent_base.Agent` and emits ordered
   `ToolCall`s in `_plan(...)`. Never call tools directly from agent
   code -- the gate must see every call.

2. **Risk policy lives in `pe_ai_agents/skills/approval_gate.py::_POLICY`.**
   When adding a new mutating tool, register it there with the right
   `(env -> RiskLevel)` mapping. Read-only tools default to LOW.

3. **Trust mode default is LOW.** Do not change defaults in
   `conf/trust_mode.yml`. Mutating actions must prompt for human
   approval until the team explicitly raises trust.

4. **Provenance is append-only.** Every tool call writes a JSONL row to
   `runs/<run_id>/provenance.jsonl` with input/output hashes, gate
   status, workstream, brand, env. Never delete or rewrite ledger rows.

5. **Brand identity is hard-coded** in
   `pe_ai_agents/skills/brand_context.py::BRAND_SPEC`. Cloning to a
   sibling repo (e.g. `pe-ai-tremfya-gi`) requires editing exactly that
   constant + KPI YAMLs + pyproject name. Do not add a "select brand at
   runtime" feature -- that's an anti-pattern here.

6. **Tools have Fake* substitutes** for tests/demos. When swapping in a
   real adapter (e.g. real Kedro), the adapter must return the same
   shape as the Fake. The Fake is the contract.

## Repo conventions

- Python >=3.10, type hints throughout.
- Tests in `tests/`, run with `pytest -q`. New code should land with
  tests. Existing tests live next to the layer they exercise (skills,
  agents, tools).
- All printable output goes via `print(...)` to stdout; the Windows
  console is cp1252 -- keep output ASCII-only (no emoji, no unicode
  arrows). Use `->` not `→`.
- New agents go in `pe_ai_agents/agents/<workstream>_<track>/`.
- New tools (= adapters over PE.AI codebase) go in `pe_ai_agents/tools/`.
- New skills (= reusable cross-agent capabilities) go in
  `pe_ai_agents/skills/`.

## Brand-specific facts (this repo)

- Brand: `tremfya`, indication: `derm`, sub-indications: `(pso, psa)`.
- Joint model: PsO + PsA are co-trained -- one
  `tremfya_pso_psa_frm_pkl_file_*.pkl` artifact, one Kedro `ds`
  pipeline run.
- Data source: IQVIA. Fulfillment window: 84 days.
- Account Prioritizer pipeline: `post_processing` (use `cross_onc` only
  for Erleada).
- Primary table for QC: `events_patient_journey_tremfya`.

## When the user asks Copilot to ...

- **"Add a new agent"**: subclass `Agent`, implement `_plan`, define
  the tools dict in `__init__`, register in
  `workspaces/{ops,dev}/cli.py`, add a test in `tests/agents/`.
- **"Add a new tool"**: write a `FakeXxx` class in
  `pe_ai_agents/tools/`, define its callable shape, add an entry to
  `_POLICY` if mutating, add a contract test in `tests/tools/`.
- **"Add a KPI"**: drop a YAML in `conf/kpi_registry/` matching the
  existing schema (`kpi_id`, `name`, `version`, `owner`, `formula`,
  `source_tables`, `brands_applicable`, `benchmark.{min,max}`).
- **"Clone to a sibling repo"**: see `README.md` ("Cloning to a sibling
  brand-therapy-area").

## Things NOT to do

- Don't add a router/conductor agent. Each workstream calls its agents
  directly via the workspace CLI.
- Don't merge `runtime/` into `skills/`. They are separate layers.
- Don't write to `conf/base/...` from agent code -- that's a HIGH-risk
  action gated through `conf_draft_pr_base`.
- Don't bypass the gate by calling `self._tools[...]` directly.
