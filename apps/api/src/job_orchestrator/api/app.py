from __future__ import annotations

import re
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from resume_engine.artifacts import ArtifactRenderer
from resume_engine.claims import (
    ApprovalScope,
    ApprovedClaim,
    ClaimLibrary,
    ProposalKind,
    ResumeProposal,
)
from resume_engine.composer import ResumeComposer
from starlette.middleware.base import BaseHTTPMiddleware

from job_orchestrator import __version__
from job_orchestrator.domain.applications import ApplicationStatus, ApplicationTask
from job_orchestrator.domain.jobs import JobPosting
from job_orchestrator.domain.screening import PRESETS
from job_orchestrator.extension.broker import ExtensionBroker
from job_orchestrator.persistence.database import Database
from job_orchestrator.persistence.repositories import (
    JobRepository,
    SettingsRepository,
    TaskRepository,
)
from job_orchestrator.persistence.resumes import (
    ClaimRepository,
    ProposalRepository,
    ResumeRecordRepository,
    proposal_payload,
    row_to_proposal,
)
from job_orchestrator.security.pairing import InvalidPairing, PairingService
from job_orchestrator.security.paths import resolve_artifact_path

from .schemas import (
    ApprovedClaimInput,
    ExtensionCommandInput,
    JobInput,
    PairingConsumeInput,
    ProposalDecisionInput,
    ResumeComposeInput,
    ResumeProposalInput,
    ScreeningSettings,
    TaskInput,
    TaskOutput,
)

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
_LOCAL_ORIGIN = re.compile(r"^https?://(?:127\.0\.0\.1|localhost)(?::\d+)?$")
_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{16,64}$")


@dataclass(frozen=True, slots=True)
class AppConfig:
    database_url: str = "sqlite:///job-orchestrator.db"
    artifact_root: Path = Path("artifacts")
    web_root: Path | None = None


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.hostname not in _LOCAL_HOSTS:
            return JSONResponse({"detail": "local loopback access only"}, status_code=403)
        return await call_next(request)


class LocalCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        allowed = bool(_LOCAL_ORIGIN.fullmatch(origin) or _EXTENSION_ORIGIN.fullmatch(origin))
        if request.method == "OPTIONS" and allowed:
            response: Response = Response(status_code=204)
        else:
            response = await call_next(request)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
            response.headers["Vary"] = "Origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response


def _preset_payload() -> dict[str, dict]:
    payload: dict[str, dict] = {}
    for name, preset in PRESETS.items():
        values = asdict(preset)
        for field_name in (
            "locations",
            "excluded_companies",
            "required_keywords",
            "excluded_keywords",
            "experiences",
            "educations",
        ):
            values[field_name] = sorted(values[field_name])
        payload[name] = values
    return payload


def _default_screening_settings() -> dict:
    return {
        "selected_preset": "precise",
        "automation_mode": "confirm_before_apply",
        "profile": _preset_payload()["precise"],
    }


def _contains_cookie_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            "cookie" in str(key).casefold() or _contains_cookie_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_cookie_key(child) for child in value)
    return False


def create_app(config: AppConfig | None = None) -> FastAPI:
    active_config = config or AppConfig()
    active_config.artifact_root.mkdir(parents=True, exist_ok=True)
    database = Database(active_config.database_url)
    database.create_schema()
    pairing = PairingService()
    broker = ExtensionBroker()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        database.dispose()

    app = FastAPI(
        title="AI Job Orchestrator CN",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.pairing = pairing
    app.state.extension_broker = broker
    app.add_middleware(LocalCorsMiddleware)
    app.add_middleware(LocalOnlyMiddleware)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/screening/presets")
    def screening_presets() -> dict[str, dict]:
        return _preset_payload()

    @app.get("/api/settings/screening", response_model=ScreeningSettings)
    def get_screening_settings() -> dict:
        return SettingsRepository(database).get("screening") or _default_screening_settings()

    @app.put("/api/settings/screening", response_model=ScreeningSettings)
    def put_screening_settings(data: ScreeningSettings) -> dict:
        payload = data.model_dump(mode="json")
        SettingsRepository(database).set("screening", payload)
        return payload

    @app.post("/api/claims", status_code=201)
    def create_claim(data: ApprovedClaimInput) -> dict:
        claim = ApprovedClaim(**data.model_dump())
        ClaimRepository(database).upsert(claim)
        return asdict(claim)

    @app.get("/api/claims")
    def list_claims() -> list[dict]:
        return [asdict(claim) for claim in ClaimRepository(database).list()]

    @app.post("/api/proposals", status_code=201)
    def create_proposal(data: ResumeProposalInput) -> dict:
        proposal = ResumeProposal(
            id=data.id,
            kind=ProposalKind(data.kind),
            target_section=data.target_section,
            proposed_text=data.proposed_text,
            source_claim_ids=tuple(data.source_claim_ids),
        )
        row = ProposalRepository(database).upsert(data.job_id, proposal)
        return proposal_payload(row)

    @app.get("/api/proposals")
    def list_proposals(job_id: str | None = None) -> list[dict]:
        return [
            proposal_payload(row)
            for row in ProposalRepository(database).list(job_id=job_id)
        ]

    @app.post("/api/proposals/{proposal_id}/decision")
    def decide_proposal(proposal_id: str, data: ProposalDecisionInput) -> dict:
        repository = ProposalRepository(database)
        row = repository.decide(proposal_id, data.decision)
        if row is None:
            raise HTTPException(404, "proposal not found")
        if data.decision == "approve_fact_library":
            ClaimRepository(database).upsert(
                ApprovedClaim(
                    id=f"proposal:{row.id}",
                    category=row.target_section,
                    statement=row.proposed_text,
                    evidence="人工批准的简历建议",
                )
            )
        return proposal_payload(row)

    @app.post("/api/resumes/compose", status_code=201)
    def compose_resume(data: ResumeComposeInput) -> dict:
        claim_library = ClaimLibrary(ClaimRepository(database).list())
        proposal_rows = ProposalRepository(database).get_many(data.proposal_ids)
        if len(proposal_rows) != len(data.proposal_ids):
            raise HTTPException(404, "one or more proposals were not found")
        proposals: list[ResumeProposal] = []
        for row in proposal_rows:
            proposal = row_to_proposal(row)
            if proposal.status.value == "approved_current_job":
                claim_library.approve(
                    proposal,
                    ApprovalScope.CURRENT_JOB,
                    job_id=row.approved_job_id or row.job_id,
                )
            proposals.append(proposal)

        records = ResumeRecordRepository(database)
        version = records.next_version(data.job_id)
        document = ResumeComposer(claim_library).compose(
            job_id=data.job_id,
            version=version,
            base_sections=data.base_sections,
            proposals=proposals,
            conservative=data.conservative,
        )
        job_directory = sha256(data.job_id.encode("utf-8")).hexdigest()[:16]
        rendered = ArtifactRenderer().render(
            document,
            active_config.artifact_root / job_directory,
        )
        resume_id = str(uuid4())
        artifact_records: list[dict] = []
        artifact_payloads: list[dict] = []
        for artifact in rendered:
            relative_path = (
                Path(artifact.path)
                .resolve()
                .relative_to(active_config.artifact_root.resolve())
                .as_posix()
            )
            artifact_id = str(uuid4())
            artifact_records.append(
                {
                    "id": artifact_id,
                    "format": artifact.format,
                    "path": artifact.path,
                    "sha256": artifact.sha256,
                }
            )
            artifact_payloads.append(
                {
                    "id": artifact_id,
                    "format": artifact.format,
                    "sha256": artifact.sha256,
                    "path": relative_path,
                    "download_url": f"/api/artifacts/{quote(relative_path, safe='/')}",
                }
            )
        source_claim_ids = sorted(
            {
                claim_id
                for proposal in proposals
                if proposal.id in document.included_proposal_ids
                for claim_id in proposal.source_claim_ids
            }
        )
        records.save(
            resume_id=resume_id,
            job_id=data.job_id,
            version=version,
            template=data.template,
            content={
                "sections": document.sections,
                "included_proposal_ids": document.included_proposal_ids,
                "excluded_proposal_ids": document.excluded_proposal_ids,
            },
            source_claim_ids=source_claim_ids,
            artifacts=artifact_records,
        )
        return {
            "id": resume_id,
            "job_id": data.job_id,
            "version": version,
            "included_proposal_ids": list(document.included_proposal_ids),
            "excluded_proposal_ids": list(document.excluded_proposal_ids),
            "artifacts": artifact_payloads,
        }

    @app.post("/api/jobs", status_code=201)
    def create_job(data: JobInput) -> dict:
        values = data.model_dump()
        values["url"] = str(values["url"])
        job = JobPosting(**values)
        JobRepository(database).upsert(job)
        return jsonable_encoder(asdict(job))

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [jsonable_encoder(asdict(item)) for item in JobRepository(database).list()]

    @app.post("/api/tasks", response_model=TaskOutput, status_code=201)
    def create_task(data: TaskInput) -> ApplicationTask:
        task = ApplicationTask(id=str(uuid4()), **data.model_dump())
        TaskRepository(database).save(task)
        return task

    @app.get("/api/tasks", response_model=list[TaskOutput])
    def list_tasks() -> list[ApplicationTask]:
        return TaskRepository(database).list()

    @app.post("/api/tasks/{task_id}/approve", response_model=TaskOutput)
    def approve_task(task_id: str) -> ApplicationTask:
        repository = TaskRepository(database)
        task = repository.get(task_id)
        if task is None:
            raise HTTPException(404, "task not found")
        if task.status is ApplicationStatus.QUEUED:
            task.transition(ApplicationStatus.PREPARING)
            task.transition(ApplicationStatus.READY_FOR_CONFIRMATION)
        try:
            task.approve()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        repository.save(task)
        return task

    @app.post("/api/tasks/{task_id}/risk-reset", response_model=TaskOutput)
    def risk_reset(task_id: str) -> ApplicationTask:
        repository = TaskRepository(database)
        task = repository.get(task_id)
        if task is None:
            raise HTTPException(404, "task not found")
        try:
            task.manual_reset()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        repository.save(task)
        return task

    @app.post("/api/pairing/token")
    def issue_pairing_token() -> dict[str, str | int]:
        return {"token": pairing.issue_token(), "expires_in_seconds": 300}

    @app.post("/api/pairing/consume")
    def consume_pairing_token(
        data: PairingConsumeInput, origin: str = Header(default="", alias="Origin")
    ) -> dict[str, str]:
        try:
            session_token = pairing.consume_token(data.token, origin=origin)
        except InvalidPairing as exc:
            raise HTTPException(403, str(exc)) from exc
        return {
            "session_token": session_token,
            "websocket_url": "ws://127.0.0.1:8765/ws/extension",
        }

    @app.get("/api/extension/status")
    def extension_status() -> dict:
        return broker.status()

    @app.post("/api/extension/commands")
    async def extension_command(data: ExtensionCommandInput) -> object:
        if _contains_cookie_key(data.payload):
            raise HTTPException(400, "cookie payloads are forbidden")
        try:
            return await broker.send_command(
                data.type,
                data.payload,
                timeout_seconds=data.timeout_seconds,
            )
        except ConnectionError as exc:
            raise HTTPException(503, str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(504, "extension command timed out") from exc

    @app.get("/api/artifacts/{relative_path:path}")
    def artifact(relative_path: str) -> FileResponse:
        try:
            path = resolve_artifact_path(active_config.artifact_root, relative_path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "artifact not found") from exc
        return FileResponse(path, filename=path.name)

    @app.websocket("/ws/extension")
    async def extension_socket(websocket: WebSocket, session_token: str) -> None:
        origin = websocket.headers.get("origin", "")
        if websocket.url.hostname not in _LOCAL_HOSTS or not pairing.validate_session(
            session_token, origin=origin
        ):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        await broker.attach(websocket)
        try:
            while True:
                try:
                    message = await websocket.receive_json()
                except Exception:
                    break
                if message.get("type") == "heartbeat":
                    await websocket.send_json({"type": "heartbeat_ack"})
                    continue
                if _contains_cookie_key(message):
                    await websocket.send_json(
                        {
                            "command_id": message.get("command_id"),
                            "status": "rejected",
                            "reason": "cookie_payload_forbidden",
                        }
                    )
                    continue
                await broker.handle_message(message)
        finally:
            await broker.detach(websocket)

    if active_config.web_root is not None and (active_config.web_root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=active_config.web_root, html=True), name="dashboard")

    return app
