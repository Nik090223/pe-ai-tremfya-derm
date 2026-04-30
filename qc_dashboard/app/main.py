"""Read-only QC dashboard backend.

Reads:
  - ``runs/qc_state.json``           -- alert feed (written by QC Watcher)
  - ``runs/<run_id>/provenance.jsonl`` -- per-run provenance entries

Exposes:
  GET  /api/health
  GET  /api/runs            -> list of run_ids with last status
  GET  /api/runs/{run_id}   -> provenance entries for one run
  GET  /api/alerts          -> all alerts in qc_state.json
  GET  /                    -> static HTML dashboard

Auth is delegated to the cluster ingress (oauth2-proxy in J&J K8s); this
backend is read-only and never writes anything to the ledger.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


def _runs_dir() -> Path:
    # Prefer env var so the K8s deployment can mount the PVC at any path.
    return Path(os.environ.get("PE_AI_RUNS_DIR", "runs"))


def _frontend_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "frontend"


app = FastAPI(title="PE.AI QC Dashboard", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    runs_dir = _runs_dir()
    return {
        "ok": True,
        "runs_dir": str(runs_dir),
        "runs_dir_exists": runs_dir.exists(),
    }


@app.get("/api/runs")
def list_runs() -> JSONResponse:
    runs_dir = _runs_dir()
    if not runs_dir.exists():
        return JSONResponse({"runs": []})
    rows = []
    for run_path in sorted(runs_dir.iterdir()):
        if not run_path.is_dir():
            continue
        prov = run_path / "provenance.jsonl"
        if not prov.exists():
            continue
        last = _last_line(prov)
        rows.append(
            {
                "run_id": run_path.name,
                "last_action": (last or {}).get("action"),
                "last_actor": (last or {}).get("actor"),
                "last_ts": (last or {}).get("ts"),
                "last_gate_status": (last or {}).get("gate_status"),
                "brand": (last or {}).get("brand"),
                "env": (last or {}).get("env"),
            }
        )
    return JSONResponse({"runs": rows})


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> JSONResponse:
    runs_dir = _runs_dir()
    prov = runs_dir / run_id / "provenance.jsonl"
    if not prov.exists():
        raise HTTPException(status_code=404, detail=f"unknown run_id {run_id!r}")
    entries = []
    with prov.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return JSONResponse({"run_id": run_id, "entries": entries})


@app.get("/api/alerts")
def list_alerts() -> JSONResponse:
    state = _runs_dir() / "qc_state.json"
    if not state.exists():
        return JSONResponse({"alerts": []})
    data = json.loads(state.read_text(encoding="utf-8"))
    return JSONResponse(data)


# Static frontend (mounted last so /api/* routes win).
_FRONTEND = _frontend_dir()
if _FRONTEND.exists():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")


def _last_line(path: Path) -> dict | None:
    last = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    return json.loads(last) if last else None
