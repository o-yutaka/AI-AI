from fastapi import FastAPI, HTTPException

from control_plane.models import DecisionTrace, RunRequest
from control_plane.runtime import AgentRuntime

app = FastAPI(
    title="AI Agent Control Plane",
    version="0.1.0",
    description="Auditable reference runtime for stateful, approval-aware AI agents.",
)
runtime = AgentRuntime()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/runs", response_model=DecisionTrace)
def create_run(request: RunRequest) -> DecisionTrace:
    return runtime.create_run(request)


@app.get("/v1/runs/{run_id}", response_model=DecisionTrace)
def get_run(run_id: str) -> DecisionTrace:
    try:
        return runtime.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/approve", response_model=DecisionTrace)
def approve_run(run_id: str) -> DecisionTrace:
    try:
        return runtime.approve(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
