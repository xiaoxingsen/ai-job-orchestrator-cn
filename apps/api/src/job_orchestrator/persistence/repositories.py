from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import select

from job_orchestrator.domain.applications import (
    ApplicationStatus,
    ApplicationTask,
    AutomationMode,
)
from job_orchestrator.domain.jobs import JobPosting

from .database import Database
from .models import ApplicationTaskRow, CommandRow, JobRow, SettingRow


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, job: JobPosting) -> None:
        with self.database.session() as session:
            row = session.scalar(
                select(JobRow).where(
                    JobRow.platform == job.platform,
                    JobRow.platform_job_id == job.platform_job_id,
                )
            )
            if row is None:
                row = JobRow(platform=job.platform, platform_job_id=job.platform_job_id)
                session.add(row)
            for name in (
                "url",
                "company",
                "title",
                "description",
                "salary_min_k",
                "salary_max_k",
                "location",
                "experience",
                "education",
                "hr_active_at",
                "snapshot_at",
            ):
                setattr(row, name, getattr(job, name))

    def get_by_platform_id(self, platform: str, platform_job_id: str) -> JobPosting | None:
        with self.database.session() as session:
            row = session.scalar(
                select(JobRow).where(
                    JobRow.platform == platform,
                    JobRow.platform_job_id == platform_job_id,
                )
            )
            return self._to_domain(row) if row else None

    def list(self) -> list[JobPosting]:
        with self.database.session() as session:
            rows = session.scalars(select(JobRow).order_by(JobRow.snapshot_at.desc())).all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: JobRow) -> JobPosting:
        return JobPosting(
            platform=row.platform,
            platform_job_id=row.platform_job_id,
            url=row.url,
            company=row.company,
            title=row.title,
            description=row.description,
            salary_min_k=row.salary_min_k,
            salary_max_k=row.salary_max_k,
            location=row.location,
            experience=row.experience,
            education=row.education,
            hr_active_at=_utc(row.hr_active_at),
            snapshot_at=_utc(row.snapshot_at),  # type: ignore[arg-type]
        )


class TaskRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, task: ApplicationTask) -> None:
        now = datetime.now(UTC)
        with self.database.session() as session:
            row = session.get(ApplicationTaskRow, task.id)
            if row is None:
                row = ApplicationTaskRow(id=task.id, created_at=now)
                session.add(row)
            row.job_id = task.job_id
            row.resume_version_id = task.resume_version_id
            row.greeting = task.greeting
            row.mode = task.mode.value
            row.platform = task.platform
            row.status = task.status.value
            row.approved = task.approved
            row.last_error = task.last_error
            row.history_json = json.dumps([status.value for status in task.history])
            row.updated_at = now

    def get(self, task_id: str) -> ApplicationTask | None:
        with self.database.session() as session:
            row = session.get(ApplicationTaskRow, task_id)
            return self._to_domain(row) if row else None

    def list(self) -> list[ApplicationTask]:
        with self.database.session() as session:
            rows = session.scalars(
                select(ApplicationTaskRow).order_by(ApplicationTaskRow.created_at.desc())
            ).all()
            return [self._to_domain(row) for row in rows]

    def recoverable_tasks(self) -> list[ApplicationTask]:
        terminal = {
            ApplicationStatus.SUBMITTED.value,
            ApplicationStatus.PREPARED.value,
            ApplicationStatus.FAILED.value,
        }
        with self.database.session() as session:
            rows = session.scalars(
                select(ApplicationTaskRow).where(ApplicationTaskRow.status.not_in(terminal))
            ).all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: ApplicationTaskRow) -> ApplicationTask:
        task = ApplicationTask(
            id=row.id,
            job_id=row.job_id,
            resume_version_id=row.resume_version_id,
            greeting=row.greeting,
            mode=AutomationMode(row.mode),
            platform=row.platform,
            status=ApplicationStatus(row.status),
            approved=row.approved,
            last_error=row.last_error,
        )
        task.history = [ApplicationStatus(value) for value in json.loads(row.history_json)]
        return task


T = TypeVar("T")


class CommandRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def execute_once(self, command_id: str, platform: str, operation: Callable[[], T]) -> T:
        with self.database.session() as session:
            existing = session.get(CommandRow, command_id)
            if existing is not None:
                if existing.status == "completed" and existing.result_json is not None:
                    return json.loads(existing.result_json)
                return {  # type: ignore[return-value]
                    "status": "unknown",
                    "recovery": "observe_result",
                    "command_id": command_id,
                }
            session.add(
                CommandRow(
                    command_id=command_id,
                    platform=platform,
                    status="pending",
                    created_at=datetime.now(UTC),
                )
            )

        result = operation()
        with self.database.session() as session:
            row = session.get(CommandRow, command_id)
            if row is None:  # pragma: no cover - database corruption guard
                raise RuntimeError("command reservation disappeared")
            row.status = "completed"
            row.result_json = json.dumps(result, ensure_ascii=False)
            row.completed_at = datetime.now(UTC)
        return result


class SettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, key: str) -> dict | None:
        with self.database.session() as session:
            row = session.get(SettingRow, key)
            return json.loads(row.value_json) if row else None

    def set(self, key: str, value: dict) -> None:
        with self.database.session() as session:
            row = session.get(SettingRow, key)
            if row is None:
                row = SettingRow(key=key, value_json="{}")
                session.add(row)
            row.value_json = json.dumps(value, ensure_ascii=False)
