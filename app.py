import os

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from control_plane.errors import (
    IdempotencyConflictError,
    InvalidRunStateError,
    UnknownRunError,
)
from control_plane.models import ApprovalRequest, DecisionTrace, RunRequest
from control_plane.providers import (
    CandidatePlanner,
    OpenAICompatiblePlanner,
    PlannedRunRequest,
    ProviderError,
)
from control_plane.runtime import AgentRuntime
from control_plane.store import SQLiteRunRepository
from control_plane.tools import tool_executor_from_environment

VERSION = "0.5.0"


def runtime_from_environment() -> AgentRuntime:
    database_path = os.getenv("AGENT_DB_PATH")
    executor = tool_executor_from_environment()
    repository = SQLiteRunRepository(database_path) if database_path else None
    return AgentRuntime(executor=executor, repository=repository)


def planner_from_environment() -> CandidatePlanner | None:
    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL")
    if not base_url or not model:
        return None
    return OpenAICompatiblePlanner(
        base_url=base_url,
        model=model,
        api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
        timeout_seconds=float(os.getenv("OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "30")),
        max_response_bytes=int(
            os.getenv("OPENAI_COMPATIBLE_MAX_RESPONSE_BYTES", "524288")
        ),
    )


def create_app(
    runtime: AgentRuntime | None = None,
    planner: CandidatePlanner | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AI Agent Control Plane",
        version=VERSION,
        description=(
            "Contract-aware, auditable reference runtime for stateful, "
            "approval-aware AI agents."
        ),
    )
    agent_runtime = runtime or runtime_from_environment()
    candidate_planner = planner or planner_from_environment()
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

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    @app.get("/v1/provider")
    def provider_status() -> dict[str, str | bool | None]:
        return {
            "configured": candidate_planner is not None,
            "provider": getattr(candidate_planner, "provider_name", None),
            "model": getattr(candidate_planner, "model", None),
        }

    @app.post(
        "/v1/agent-runs",
        response_model=DecisionTrace,
        status_code=status.HTTP_201_CREATED,
    )
    def create_planned_run(request: PlannedRunRequest) -> DecisionTrace:
        if candidate_planner is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "OpenAI-compatible planner is not configured; set "
                    "OPENAI_COMPATIBLE_BASE_URL and OPENAI_COMPATIBLE_MODEL"
                ),
            )
        try:
            plan = candidate_planner.plan(request)
            return agent_runtime.create_run(
                RunRequest(
                    goal=request.goal,
                    observation={
                        **request.observation,
                        "_planner": {
                            "provider": plan.provider,
                            "model": plan.model,
                        },
                    },
                    contract=request.contract,
                    candidates=plan.candidates,
                    idempotency_key=request.idempotency_key,
                )
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
