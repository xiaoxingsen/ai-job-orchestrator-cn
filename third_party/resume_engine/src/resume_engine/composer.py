from __future__ import annotations

from dataclasses import dataclass

from .claims import ClaimLibrary, ProposalKind, ResumeProposal


@dataclass(frozen=True, slots=True)
class ResumeDocument:
    job_id: str
    version: int
    sections: dict[str, tuple[str, ...]]
    included_proposal_ids: tuple[str, ...]
    excluded_proposal_ids: tuple[str, ...]

    @property
    def plain_text(self) -> str:
        blocks: list[str] = []
        for heading, lines in self.sections.items():
            blocks.append(heading)
            blocks.extend(lines)
        return "\n".join(blocks)


class ResumeComposer:
    def __init__(self, claims: ClaimLibrary) -> None:
        self.claims = claims

    def compose(
        self,
        *,
        job_id: str,
        version: int,
        base_sections: dict[str, list[str]],
        proposals: list[ResumeProposal],
        conservative: bool = False,
    ) -> ResumeDocument:
        if version < 1:
            raise ValueError("resume versions start at 1")
        sections = {heading: list(lines) for heading, lines in base_sections.items()}
        included: list[str] = []
        excluded: list[str] = []

        for proposal in proposals:
            include = False
            if proposal.kind is ProposalKind.SAFE_REWRITE:
                include = self.claims.has_claims(proposal.source_claim_ids)
            elif proposal.kind is ProposalKind.PENDING_CLAIM:
                include = self.claims.is_proposal_approved_for(proposal, job_id)
            # gap warnings are advisory and never enter a resume.
            if include:
                sections.setdefault(proposal.target_section, []).append(proposal.proposed_text)
                included.append(proposal.id)
            else:
                excluded.append(proposal.id)

        return ResumeDocument(
            job_id=job_id,
            version=version,
            sections={heading: tuple(lines) for heading, lines in sections.items()},
            included_proposal_ids=tuple(included),
            excluded_proposal_ids=tuple(excluded),
        )

