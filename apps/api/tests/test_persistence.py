from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from job_orchestrator.domain.applications import (
    ApplicationStatus,
    ApplicationTask,
    AutomationMode,
    RecoveryAction,
)
from job_orchestrator.domain.jobs import JobPosting
from job_orchestrator.persistence.database import Database
from job_orchestrator.persistence.repositories import (
    CommandRepository,
    JobRepository,
    TaskRepository,
)


def database(tmp_path: Path) -> Database:
    db = Database(f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    db.create_schema()
    return db


def job() -> JobPosting:
    return JobPosting(
        platform="boss",
        platform_job_id="boss-1",
        url="https://www.zhipin.com/job_detail/boss-1.html",
        company="本地科技",
        title="后端工程师",
        description="FastAPI 与 SQLite",
        salary_min_k=20,
        salary_max_k=30,
        location="深圳",
        experience="3-5年",
        education="本科",
        hr_active_at=datetime.now(UTC),
        snapshot_at=datetime.now(UTC),
    )


def application() -> ApplicationTask:
    return ApplicationTask(
        id=str(uuid4()),
        job_id="boss-1",
        resume_version_id="resume-v1",
        greeting="您好，期待沟通。",
        mode=AutomationMode.AUTO_APPLY,
        platform="boss",
    )


def test_jobs_and_tasks_survive_database_reopen(tmp_path: Path) -> None:
    first = database(tmp_path)
    JobRepository(first).upsert(job())
    item = application()
    item.transition(ApplicationStatus.PREPARING)
    TaskRepository(first).save(item)
    first.dispose()

    reopened = database(tmp_path)
    stored_job = JobRepository(reopened).get_by_platform_id("boss", "boss-1")
    stored_task = TaskRepository(reopened).get(item.id)

    assert stored_job is not None
    assert stored_job.company == "本地科技"
    assert stored_task is not None
    assert stored_task.status is ApplicationStatus.PREPARING
    assert stored_task.mode is AutomationMode.AUTO_APPLY


def test_submitting_task_recovers_by_observation_not_replay(tmp_path: Path) -> None:
    db = database(tmp_path)
    item = application()
    item.status = ApplicationStatus.SUBMITTING
    TaskRepository(db).save(item)

    recovered = TaskRepository(db).recoverable_tasks()

    assert len(recovered) == 1
    assert recovered[0].recovery_action() is RecoveryAction.OBSERVE_RESULT


def test_command_idempotency_is_persisted(tmp_path: Path) -> None:
    db = database(tmp_path)
    repository = CommandRepository(db)
    calls = 0

    def submit() -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "submitted", "remote_id": "chat-7"}

    command_id = str(uuid4())
    first = repository.execute_once(command_id, "boss", submit)
    db.dispose()

    reopened = database(tmp_path)
    second = CommandRepository(reopened).execute_once(command_id, "boss", submit)

    assert first == second
    assert calls == 1

