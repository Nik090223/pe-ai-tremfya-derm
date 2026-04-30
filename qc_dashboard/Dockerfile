# PE.AI QC Dashboard
# Read-only FastAPI app that surfaces provenance + alerts.
# Build:  docker build -t pe-ai-qc:dev qc_dashboard
# Run:    docker run --rm -p 8000:8000 -v "$PWD/runs:/app/runs" pe-ai-qc:dev

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PE_AI_RUNS_DIR=/app/runs

WORKDIR /app

RUN pip install --no-cache-dir "fastapi==0.110.*" "uvicorn==0.27.*"

COPY app/ ./app/
COPY frontend/ ./frontend/

# Provenance volume is mounted at /app/runs (PVC in K8s, bind mount locally).
VOLUME ["/app/runs"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
