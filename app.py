import os

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from control_plane.errors import (
    IdempotencyConflictError,
    InvalidRunStateError,
    UnknownRunError,
)
from control_plane.models import ApprovalRequest, DecisionTrace, RunRequest
from control_plane.runtime import AgentRuntime


def create_app(runtime: AgentRuntime | None = None) -> FastAPI:
    app = FastAPI(
        title="AI Agent Control Plane",
        version="0.2.0",
        description=(
            "Contract-aware, auditable reference runtime for stateful, "
            "approval-aware AI agents."
        ),
    )
    agent_runtime = runtime or AgentRuntime()
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.2.0"}

    @app.post(
        "/v1/runs",
        response_model=DecisionTrace,
        status_code=status.HTTP_201_CREATED,
    )
    def create_run(request: RunRequest) -> DecisionTrace:
        try:
            return agent_runtime.create_run(request)
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/runs", response_model=list[DecisionTrace])
    def list_runs() -> list[DecisionTrace]:
        return agent_runtime.list_runs()

    @app.get("/v1/runs/{run_id}", response_model=DecisionTrace)
    def get_run(run_id: str) -> DecisionTrace:
        try:
            return agent_runtime.get_run(run_id)
        except UnknownRunError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/runs/{run_id}/decision", response_model=DecisionTrace)
    def decide_run(run_id: str, request: ApprovalRequest) -> DecisionTrace:
        try:
            return agent_runtime.decide(run_id, request)
        except UnknownRunError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRunStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
