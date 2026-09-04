from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .jobs import JobPosting


@dataclass(frozen=True, slots=True)
class ScreeningProfile:
    name: str
    minimum_score: int
    daily_limit: int
    locations: set[str] = field(default_factory=set)
    salary_min_k: int | None = None
    excluded_companies: set[str] = field(default_factory=set)
    required_keywords: set[str] = field(default_factory=set)
    excluded_keywords: set[str] = field(default_factory=set)
    experiences: set[str] = field(default_factory=set)
    educations: set[str] = field(default_factory=set)
    hr_active_within_days: int | None = None
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "skills": 0.45,
            "experience": 0.25,
            "industry": 0.15,
            "education": 0.05,
            "preference": 0.10,
        }
    )


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    accepted: bool
    ai_evaluated: bool
    score: int | None
    reasons: list[str]


PRESETS: dict[str, ScreeningProfile] = {
    "precise": ScreeningProfile(
        name="precise", minimum_score=85, hr_active_within_days=7, daily_limit=10
    ),
    "balanced": ScreeningProfile(
        name="balanced", minimum_score=70, hr_active_within_days=30, daily_limit=20
    ),
    "broad": ScreeningProfile(
        name="broad", minimum_score=55, hr_active_within_days=None, daily_limit=30
    ),
}


def _hard_filter_reasons(
    job: JobPosting, profile: ScreeningProfile, *, now: datetime
) -> list[str]:
    text = f"{job.title}\n{job.description}".casefold()
    reasons: list[str] = []
    if profile.locations and job.location not in profile.locations:
        reasons.append("location_not_allowed")
    if (
        profile.salary_min_k is not None
        and job.salary_max_k is not None
        and job.salary_max_k < profile.salary_min_k
    ):
        reasons.append("salary_below_minimum")
    if job.company in profile.excluded_companies:
        reasons.append("company_excluded")
    if profile.required_keywords and not all(
        keyword.casefold() in text for keyword in profile.required_keywords
    ):
        reasons.append("required_keyword_missing")
    if any(keyword.casefold() in text for keyword in profile.excluded_keywords):
        reasons.append("excluded_keyword_present")
    if profile.experiences and job.experience not in profile.experiences:
        reasons.append("experience_not_allowed")
    if profile.educations and job.education not in profile.educations:
        reasons.append("education_not_allowed")
    if profile.hr_active_within_days is not None:
        cutoff = now - timedelta(days=profile.hr_active_within_days)
        if job.hr_active_at is None or job.hr_active_at < cutoff:
            reasons.append("hr_not_recently_active")
    return reasons


def screen_job(
    job: JobPosting,
    profile: ScreeningProfile,
    *,
    ai_score: int,
    now: datetime | None = None,
) -> ScreeningResult:
    check_time = now or datetime.now(UTC)
    reasons = _hard_filter_reasons(job, profile, now=check_time)
    if reasons:
        return ScreeningResult(False, False, None, reasons)
    if ai_score < profile.minimum_score:
        return ScreeningResult(False, True, ai_score, ["score_below_threshold"])
    return ScreeningResult(True, True, ai_score, [])

