from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from job_orchestrator.domain.applications import ApplicationStatus, AutomationMode


class JobInput(BaseModel):
    platform: str = Field(pattern=r"^(boss|liepin|zhilian|mock)$")
    platform_job_id: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=100_000)
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    location: str = Field(max_length=100)
    experience: str = Field(max_length=100)
    education: str = Field(max_length=100)
    hr_active_at: datetime | None = None
    snapshot_at: datetime


class TaskInput(BaseModel):
    job_id: str = Field(min_length=1, max_length=255)
    resume_version_id: str = Field(min_length=1, max_length=255)
    greeting: str = Field(min_length=1, max_length=500)
    mode: AutomationMode
    platform: str = Field(pattern=r"^(boss|liepin|zhilian|mock)$")


class TaskOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    resume_version_id: str
    greeting: str
    mode: AutomationMode
    platform: str
    status: ApplicationStatus
    approved: bool
    last_error: str | None


class PairingConsumeInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ExtensionCommandInput(BaseModel):
    type: Literal[
        "detectPage",
        "collectListings",
        "extractJob",
        "preflight",
        "submit",
        "observeResult",
        "stop",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30, ge=1, le=60)


class MatchWeights(BaseModel):
    skills: float = Field(ge=0, le=1)
    experience: float = Field(ge=0, le=1)
    industry: float = Field(ge=0, le=1)
    education: float = Field(ge=0, le=1)
    preference: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def total_is_one(self):
        if abs(sum(self.model_dump().values()) - 1) > 0.001:
            raise ValueError("screening weights must add up to 1")
        return self


class ScreeningProfileConfig(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    minimum_score: int = Field(ge=0, le=100)
    daily_limit: int = Field(ge=1, le=100)
    locations: list[str] = Field(default_factory=list, max_length=50)
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    excluded_companies: list[str] = Field(default_factory=list, max_length=200)
    required_keywords: list[str] = Field(default_factory=list, max_length=100)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=100)
    experiences: list[str] = Field(default_factory=list, max_length=50)
    educations: list[str] = Field(default_factory=list, max_length=50)
    hr_active_within_days: int | None = Field(default=None, ge=0, le=365)
    weights: MatchWeights


class ScreeningSettings(BaseModel):
    selected_preset: Literal["precise", "balanced", "broad", "custom"]
    automation_mode: AutomationMode
    profile: ScreeningProfileConfig


class ApprovedClaimInput(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    statement: str = Field(min_length=1, max_length=5_000)
    evidence: str = Field(min_length=1, max_length=5_000)


class ResumeProposalInput(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    job_id: str = Field(min_length=1, max_length=255)
    kind: Literal["safe_rewrite", "pending_claim", "gap_warning"]
    target_section: str = Field(min_length=1, max_length=100)
    proposed_text: str = Field(min_length=1, max_length=5_000)
    source_claim_ids: list[str] = Field(default_factory=list, max_length=100)


class ProposalDecisionInput(BaseModel):
    decision: Literal["approve_current_job", "approve_fact_library", "reject"]


class ResumeComposeInput(BaseModel):
    job_id: str = Field(min_length=1, max_length=255)
    base_sections: dict[str, list[str]]
    proposal_ids: list[str] = Field(default_factory=list, max_length=500)
    conservative: bool = True
    template: str = Field(default="default-cn", min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_sections(self):
        if len(self.base_sections) > 50:
            raise ValueError("too many resume sections")
        if any(
            len(heading) > 100 or len(lines) > 200
            for heading, lines in self.base_sections.items()
        ):
            raise ValueError("resume section exceeds limits")
        return self
