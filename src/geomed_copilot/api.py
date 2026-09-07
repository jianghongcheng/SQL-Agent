"""Authenticated SQL task submission, evidence inspection and review."""
import time
import uuid
import os
from pathlib import Path

from .backends import job_repository_from_env
from .dashboard import render_dashboard
from .metrics import HttpMetrics
from .replay import build_replay_payload, replay_guarantee
from .security import ApiKeyAuthorizer, BrowserSessions
from .sql_config import SQLTaskRegistry

LOCAL_BENCHMARK_REPORT = Path(__file__).resolve().parents[2] / 'runtime/local-demo/benchmark.html'


def create_app(jobs=None, registry=None, authorizer=None):
    from fastapi import FastAPI, Header, HTTPException, Request, Response, Cookie
    from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
    from pydantic import BaseModel, Field, ConfigDict

    jobs = jobs if jobs is not None else job_repository_from_env()
    registry = registry if registry is not None else SQLTaskRegistry.from_env()
    authorizer = authorizer if authorizer is not None else ApiKeyAuthorizer.from_env()
    sessions = BrowserSessions()
    metrics = HttpMetrics()
    app = FastAPI(title="RadMeasure SQL Data Agent", version="0.5.0")

    class JobPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        task_id: str = Field(min_length=1, max_length=128)
        question: str | None = Field(default=None, min_length=1, max_length=4000)
        initial_sql: str = Field(default="", max_length=20000)

    class ReviewPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        decision: str = Field(pattern="^(approve|reject)$")
        notes: str = Field(default="", max_length=2000)

    class LoginPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        api_key: str = Field(min_length=1, max_length=4096)

    def authorize(key, role, session=None):
        try:
            return authorizer.authenticate(key, role) if key else sessions.authenticate(session, role)
        except PermissionError as exc:
            raise HTTPException(401 if "invalid or missing" in str(exc) else 403, str(exc)) from exc

    def get(job_id):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    @app.middleware("http")
    async def observe(request: Request, call_next):
        trace = request.headers.get("x-request-id", "")
        request.state.trace_id = trace if trace and len(trace) <= 128 else str(uuid.uuid4())
        started = time.perf_counter()
        origin = request.headers.get('origin')
        if (request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.cookies.get('contractsql_session')
                and origin and origin != str(request.base_url).rstrip('/')):
            return JSONResponse({'detail': 'cross-origin session request rejected'}, status_code=403)
        response = await call_next(request)
        metrics.observe(request.method, request.url.path, response.status_code, time.perf_counter() - started)
        response.headers["x-request-id"] = request.state.trace_id
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(render_dashboard(), headers={"Cache-Control": "no-store"})

    @app.get('/benchmark', response_class=HTMLResponse, include_in_schema=False)
    def benchmark_report():
        if os.environ.get('RADMEASURE_LOCAL_DEMO') != '1' or not LOCAL_BENCHMARK_REPORT.is_file():
            raise HTTPException(404, 'local benchmark report unavailable')
        return LOCAL_BENCHMARK_REPORT.read_text()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "sql_data_agent"}

    @app.post('/v1/auth/login')
    def login(payload: LoginPayload, request: Request, response: Response):
        principal = authorize(payload.api_key, 'viewer')
        try:
            token = sessions.create(principal)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        sessions.revoke(request.cookies.get('contractsql_session'))
        response.set_cookie('contractsql_session', token, httponly=True,
                            secure=request.url.scheme == 'https', samesite='strict',
                            max_age=sessions.ttl_seconds, path='/')
        response.headers['Cache-Control'] = 'no-store'
        return {'name': principal.name, 'role': principal.role}

    @app.get('/v1/auth/session')
    def session_status(response: Response, contractsql_session: str | None = Cookie(default=None)):
        principal = authorize(None, 'viewer', contractsql_session)
        response.headers['Cache-Control'] = 'no-store'
        return {'name': principal.name, 'role': principal.role}

    @app.post('/v1/auth/logout')
    def logout(response: Response, contractsql_session: str | None = Cookie(default=None)):
        sessions.revoke(contractsql_session)
        response.delete_cookie('contractsql_session', path='/', httponly=True, samesite='strict')
        response.headers['Cache-Control'] = 'no-store'
        return {'signed_out': True}

    @app.get("/v1/tasks")
    def tasks(x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        return {"tasks": registry.describe()}

    @app.get("/v1/capabilities")
    def capabilities(x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        return {"domain": "sql", "operations": ["read_only_query", "query_repair", "contract_validation"],
                "validation_scope": "structural_contract_not_semantic_proof", "tasks": registry.describe()}

    @app.post("/v1/jobs", status_code=202)
    def submit(payload: JobPayload, request: Request,
               idempotency_key: str = Header(min_length=1, max_length=256),
               x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        principal = authorize(x_api_key, "operator", contractsql_session)
        try:
            task = registry.get(payload.task_id)
            task.validate_question(payload.question)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        content = payload.model_dump()
        content["question"] = content["question"] or task.question
        content.update(_trace_id=request.state.trace_id, _submitted_by=principal.name,
                       _execution_contract_sha256=task.contract.snapshot().sha256,
                       _business_context_sha256=task.context_sha256)
        job, created = jobs.submit("sql_analysis", content, idempotency_key)
        # A reused key is allowed only for the same task inputs.
        if any(job.payload.get(k) != content.get(k) for k in ("task_id", "question", "initial_sql", "_execution_contract_sha256", "_business_context_sha256")):
            raise HTTPException(409, "idempotency key already used for different inputs")
        return {"job": job.to_dict(), "created": created}

    @app.get("/v1/jobs/{job_id}")
    def job(job_id: str, x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        return get(job_id).to_dict()

    @app.get("/v1/jobs/{job_id}/events")
    def events(job_id: str, x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        get(job_id)
        return {"events": jobs.events(job_id)}

    @app.get("/v1/traces/{trace_id}")
    def trace(trace_id: str, x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        runs = jobs.find_by_trace_id(trace_id)
        if not runs:
            raise HTTPException(404, "trace not found")
        return {"trace_id": trace_id, "runs": [{"job": j.to_dict(), "events": jobs.events(j.job_id)} for j in runs]}

    @app.post("/v1/jobs/{job_id}/replay", status_code=202)
    def replay(job_id: str, request: Request,
               idempotency_key: str = Header(min_length=1, max_length=256),
               x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        principal = authorize(x_api_key, "operator", contractsql_session)
        original = get(job_id)
        try:
            content = build_replay_payload(original, request.state.trace_id, principal.name)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        job, created = jobs.submit("sql_analysis", content, idempotency_key, original.max_attempts)
        if job.payload.get("_replay_of_job_id") != job_id:
            raise HTTPException(409, "idempotency key already used for another request")
        return {"job": job.to_dict(), "created": created, "guarantee": replay_guarantee(original)}

    @app.post("/v1/jobs/{job_id}/review")
    def review(job_id: str, payload: ReviewPayload, x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        principal = authorize(x_api_key, "admin", contractsql_session)
        get(job_id)
        try:
            return jobs.review(job_id, principal.name, payload.decision, notes=payload.notes).to_dict()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/v1/operations")
    def operations(x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        return {"job_status_counts": jobs.status_counts()}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metric_text(x_api_key: str | None = Header(default=None),
               contractsql_session: str | None = Cookie(default=None)):
        authorize(x_api_key, "viewer", contractsql_session)
        return metrics.render(jobs.status_counts())

    return app
