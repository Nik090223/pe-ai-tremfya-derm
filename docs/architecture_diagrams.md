# PE.AI Agentic Harness -- Diagrams

GitHub renders these Mermaid diagrams inline. In VS Code, install the
"Markdown Preview Mermaid Support" extension (`bierner.markdown-mermaid`)
or use the built-in preview in recent versions.

The same diagrams apply to all three sibling repos
(`pe-ai-tremfya-derm`, `pe-ai-tremfya-gi`, `pe-ai-erleada`); only
`BRAND_SPEC` and a handful of brand-coupled paths differ. This file
lives in the reference repo (`pe-ai-tremfya-derm`).

---

## 1. System topology

Who calls what, and where the data flows.

```mermaid
flowchart TD
    Team["Brand-indication team<br/>3 ops + 3 dev (per repo)"]

    Team -->|"runs pipeline"| OpsCLI["workspaces.ops.cli"]
    Team -->|"iterates"| DevCLI["workspaces.dev.cli"]

    subgraph OpsAgents["Ops agents (4)"]
        FR["fulfillment_runner"]
        PR["persistency_runner"]
        AP["account_prioritizer<br/>post_processing or cross_onc"]
        QW["qc_watcher<br/>(always-on)"]
    end

    subgraph DevAgents["Dev agents (7)"]
        direction LR
        subgraph Enhance["enhance"]
            RT["retrainer"]
            TW["tweaker"]
        end
        subgraph Build["build"]
            CB["cohort_builder"]
            FB["feature_builder"]
            MB["model_builder"]
            QR["qc_reviewer"]
        end
        subgraph Adhoc["adhoc"]
            QA["quick_analyst"]
        end
    end

    OpsCLI --> OpsAgents
    DevCLI --> DevAgents

    OpsAgents --> AgentBase
    DevAgents --> AgentBase

    AgentBase["Agent.run() loop<br/>plan -> gate -> execute -> record"]

    AgentBase --> Tools
    AgentBase --> Skills
    AgentBase --> Ledger

    subgraph Tools["Tools = adapters over PE.AI codebase"]
        Kedro["kedro"]
        Argo["argo"]
        DQM["dqm"]
        DB["db"]
        Journey["journey"]
        Conf["conf"]
        Email["email"]
    end

    subgraph Skills["Skills = cross-agent capabilities"]
        BC["brand_context"]
        AG["approval_gate"]
        KR["kpi_registry"]
        MT["mlflow_tracker"]
        AL["alerts"]
        PV["provenance"]
    end

    Tools -->|"thin adapters"| PEAI["PE.AI codebase<br/>Kedro 0.18 + Argo + Spark"]

    Ledger["runs/run_id/provenance.jsonl<br/>(append-only, sha256)"]
    AlertSink["runs/qc_state.json<br/>(rolling alert feed)"]
    QW --> AlertSink

    Ledger --> Dashboard
    AlertSink --> Dashboard["QC Dashboard<br/>FastAPI on K8s<br/>shared RWX PVC"]
    Dashboard --> Ops["Ops team monitoring"]

    TrustConf["conf/trust_mode.yml<br/>ops: LOW / dev: LOW"] -.-> AgentBase
```

---

## 2. Plan -> gate -> execute -> record (one tool call)

What happens inside `Agent.run()` for every `ToolCall` the agent emits.

```mermaid
sequenceDiagram
    autonumber
    participant U as Operator
    participant CLI as Workspace CLI
    participant Agent as Agent subclass
    participant Gate as ApprovalGate
    participant Tool as Tool adapter
    participant Ledger as Provenance ledger

    U->>CLI: pe-ai-ops fulfillment_runner --env dev
    CLI->>Agent: agent.run(workspace, request)
    Agent->>Ledger: record "dispatch"

    loop for each ToolCall in _plan(ctx, request)
        Agent->>Gate: gate.run(call, ctx, execute_fn)

        alt risk = LOW (read-only)
            Gate->>Tool: execute_fn()
            Tool-->>Gate: result
            Gate-->>Agent: (result, "auto-low")

        else mutation under LOW trust
            Gate->>U: PROMPT: approve "kedro_run" in env=dev?
            alt user types y
                U-->>Gate: yes
                Gate->>Tool: execute_fn()
                Tool-->>Gate: result
                Gate-->>Agent: (result, "human-approved")
            else user types n
                U-->>Gate: no
                Gate-->>Agent: raise ApprovalDenied
                Agent->>Ledger: record gate_status="denied"
                Note over Agent: soft-fail, continue to next call
            end

        else risk = HIGH or env=prod
            Gate->>U: PROMPT (always)
            U-->>Gate: y/n
        end

        Agent->>Ledger: record tool call + result + gate_status
    end

    Agent-->>CLI: AgentResult(ok, summary, artifacts, denied_calls)
    CLI-->>U: print summary
```

---

## 3. Ops weekly flow

```mermaid
flowchart LR
    Mon["Mon AM<br/>kickoff"]
    Mon --> FR["fulfillment_runner<br/>kedro ds (model=fulfillment)"]
    FR --> PR["persistency_runner<br/>kedro ds (model=persistency)"]
    PR --> AP["account_prioritizer<br/>post_processing / cross_onc"]
    AP --> Output["scored accounts<br/>+ top-N prioritization"]

    QW["qc_watcher<br/>K8s CronJob, every 30 min"]
    QW --> Alerts["runs/qc_state.json"]
    Alerts --> Dashboard["QC Dashboard"]

    Output --> Dashboard
    Dashboard --> Ops["Ops team monitoring"]
    Ops -->|"if metrics drift"| Esc["escalate to Dev<br/>(retrainer or QC reviewer)"]
```

---

## 4. Dev build track flow (new model end-to-end)

```mermaid
flowchart LR
    Start["Dev build operator"]
    Start --> CB["cohort_builder<br/>journey_load per sub_indication"]
    CB --> FB["feature_builder<br/>draft feature YAML +<br/>KPI registration proposal"]
    FB --> MB["model_builder<br/>kedro ds (mode=candidate)<br/>+ mlflow_log"]
    MB --> QR["qc_reviewer<br/>compare metrics vs<br/>KPI benchmarks"]
    QR -->|"ok=true"| Promote["HIGH-risk handoff:<br/>mlflow_promote (gated)"]
    QR -->|"ok=false"| Iterate["iterate"]
    Iterate --> FB
    Promote --> Ops["handed to Ops"]
```

---

## 5. Risk + trust decision matrix

How the gate decides whether to auto-execute or prompt the human.

```mermaid
flowchart TD
    Call["incoming ToolCall<br/>(tool, env, declared risk)"]
    Call --> Lookup["lookup risk in _POLICY<br/>(tool, env) -> RiskLevel"]
    Lookup --> MaxRisk["effective_risk = max(declared, policy)"]

    MaxRisk --> Trust{"trust mode<br/>for workstream?"}

    Trust -->|"LOW (default)"| LowBranch{"effective_risk?"}
    LowBranch -->|"LOW"| Auto1["auto-execute<br/>gate_status=auto-low"]
    LowBranch -->|"MEDIUM or HIGH"| Prompt1["PROMPT human"]

    Trust -->|"MEDIUM"| MedBranch{"effective_risk + env?"}
    MedBranch -->|"LOW or MEDIUM in non-prod"| Auto2["auto-execute"]
    MedBranch -->|"HIGH or env=prod"| Prompt2["PROMPT human"]

    Trust -->|"HIGH"| HighBranch{"effective_risk?"}
    HighBranch -->|"LOW or MEDIUM"| Auto3["auto-execute"]
    HighBranch -->|"HIGH"| Prompt3["PROMPT human"]

    Prompt1 --> User{"user approves?"}
    Prompt2 --> User
    Prompt3 --> User
    User -->|"yes"| Exec["execute<br/>gate_status=human-approved"]
    User -->|"no"| Deny["raise ApprovalDenied<br/>gate_status=denied"]
```

---

## 6. Repo topology (3 brand-indication repos)

```mermaid
flowchart TD
    subgraph Repos["pe-ai-repos/"]
        Derm["pe-ai-tremfya-derm<br/>indication=derm<br/>sub=(pso, psa)<br/>insights model"]
        GI["pe-ai-tremfya-gi<br/>indication=gi<br/>sub=(uc, cd)<br/>FRM model"]
        Erleada["pe-ai-erleada<br/>indication=oncology<br/>sub=(pc,)<br/>cross_onc + SHS"]
    end

    Common["Identical: agents, runtime,<br/>tools, skills, dashboard"]
    Diff["Brand-coupled: BRAND_SPEC,<br/>KPI YAMLs, primary table,<br/>account_prioritizer pipeline_name"]

    Derm -.-> Common
    GI -.-> Common
    Erleada -.-> Common

    Derm -.-> Diff
    GI -.-> Diff
    Erleada -.-> Diff

    Future["Future: extract shared bits to<br/>pe-ai-harness as versioned lib<br/>once 2-3 repos are stable"]
    Common -.-> Future
```
