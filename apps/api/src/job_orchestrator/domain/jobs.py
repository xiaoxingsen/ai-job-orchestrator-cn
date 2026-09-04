from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class JobPosting:
    platform: str
    platform_job_id: str
    url: str
    company: str
    title: str
    description: str
    salary_min_k: int | None
    salary_max_k: int | None
    location: str
    experience: str
    education: str
    hr_active_at: datetime | None
    snapshot_at: datetime

    @property
    def canonical_url(self) -> str:
        parts = urlsplit(self.url)
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))

    @property
    def deduplication_key(self) -> tuple[str, str]:
        if self.platform_job_id:
            return self.platform.lower(), f"id:{self.platform_job_id}"
        return self.platform.lower(), f"url:{self.canonical_url}"


def deduplicate_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """Keep the newest snapshot while preserving first-seen key order."""
    latest: dict[tuple[str, str], JobPosting] = {}
    key_order: list[tuple[str, str]] = []
    for job in jobs:
        key = job.deduplication_key
        if key not in latest:
            key_order.append(key)
        if key not in latest or job.snapshot_at >= latest[key].snapshot_at:
            latest[key] = job
    return [latest[key] for key in key_order]

