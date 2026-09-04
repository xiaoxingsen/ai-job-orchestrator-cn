from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ProposalKind(StrEnum):
    SAFE_REWRITE = "safe_rewrite"
    PENDING_CLAIM = "pending_claim"
    GAP_WARNING = "gap_warning"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED_CURRENT_JOB = "approved_current_job"
    APPROVED_FACT_LIBRARY = "approved_fact_library"
    REJECTED = "rejected"


class ApprovalScope(StrEnum):
    CURRENT_JOB = "current_job"
    FACT_LIBRARY = "fact_library"


@dataclass(frozen=True, slots=True)
class ApprovedClaim:
    id: str
    category: str
    statement: str
    evidence: str


@dataclass(slots=True)
class ResumeProposal:
    id: str
    kind: ProposalKind
    target_section: str
    proposed_text: str
    source_claim_ids: tuple[str, ...] = ()
    status: ProposalStatus = ProposalStatus.PENDING


def _fingerprint(text: str) -> str:
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE).casefold()


class ClaimLibrary:
    def __init__(self, claims: list[ApprovedClaim] | None = None) -> None:
        self._claims = {item.id: item for item in claims or []}
        self._job_approvals: dict[str, str] = {}
        self._negative_memory: set[str] = set()

    @property
    def claims(self) -> tuple[ApprovedClaim, ...]:
        return tuple(self._claims.values())

    def has_claims(self, claim_ids: tuple[str, ...]) -> bool:
        return bool(claim_ids) and all(claim_id in self._claims for claim_id in claim_ids)

    def approve(
        self, proposal: ResumeProposal, scope: ApprovalScope, *, job_id: str
    ) -> ApprovedClaim | None:
        if proposal.kind is ProposalKind.GAP_WARNING:
            raise ValueError("gap warnings cannot become resume claims")
        if scope is ApprovalScope.CURRENT_JOB:
            proposal.status = ProposalStatus.APPROVED_CURRENT_JOB
            self._job_approvals[proposal.id] = job_id
            return None
        proposal.status = ProposalStatus.APPROVED_FACT_LIBRARY
        self._job_approvals.pop(proposal.id, None)
        approved = ApprovedClaim(
            id=f"proposal:{proposal.id}",
            category=proposal.target_section,
            statement=proposal.proposed_text,
            evidence="人工批准的简历建议",
        )
        self._claims[approved.id] = approved
        return approved

    def reject(self, proposal: ResumeProposal) -> None:
        proposal.status = ProposalStatus.REJECTED
        self._job_approvals.pop(proposal.id, None)
        self._negative_memory.add(_fingerprint(proposal.proposed_text))

    def is_proposal_approved_for(self, proposal: ResumeProposal, job_id: str) -> bool:
        if proposal.status is ProposalStatus.APPROVED_FACT_LIBRARY:
            return True
        return (
            proposal.status is ProposalStatus.APPROVED_CURRENT_JOB
            and self._job_approvals.get(proposal.id) == job_id
        )

    def should_suggest(self, text: str) -> bool:
        return _fingerprint(text) not in self._negative_memory

