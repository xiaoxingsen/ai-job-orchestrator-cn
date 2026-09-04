from __future__ import annotations

import json
from datetime import UTC, datetime

from resume_engine.claims import ApprovedClaim, ProposalKind, ProposalStatus, ResumeProposal
from sqlalchemy import func, select

from .database import Database
from .models import ApprovedClaimRow, ArtifactRow, ResumeProposalRow, ResumeVersionRow


class ClaimRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, claim: ApprovedClaim) -> ApprovedClaim:
        with self.database.session() as session:
            row = session.get(ApprovedClaimRow, claim.id)
            if row is None:
                row = ApprovedClaimRow(id=claim.id, created_at=datetime.now(UTC))
                session.add(row)
            row.category = claim.category
            row.statement = claim.statement
            row.evidence = claim.evidence
        return claim

    def list(self) -> list[ApprovedClaim]:
        with self.database.session() as session:
            rows = session.scalars(
                select(ApprovedClaimRow).order_by(ApprovedClaimRow.created_at)
            ).all()
            return [
                ApprovedClaim(
                    id=row.id,
                    category=row.category,
                    statement=row.statement,
                    evidence=row.evidence,
                )
                for row in rows
            ]


class ProposalRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, job_id: str, proposal: ResumeProposal) -> ResumeProposalRow:
        with self.database.session() as session:
            row = session.get(ResumeProposalRow, proposal.id)
            if row is None:
                row = ResumeProposalRow(id=proposal.id)
                session.add(row)
            row.job_id = job_id
            row.kind = proposal.kind.value
            row.target_section = proposal.target_section
            row.proposed_text = proposal.proposed_text
            row.source_claim_ids_json = json.dumps(proposal.source_claim_ids, ensure_ascii=False)
            row.status = proposal.status.value
            row.approved_job_id = None
        return self.get(proposal.id)  # type: ignore[return-value]

    def get(self, proposal_id: str) -> ResumeProposalRow | None:
        with self.database.session() as session:
            row = session.get(ResumeProposalRow, proposal_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def list(self, *, job_id: str | None = None) -> list[ResumeProposalRow]:
        with self.database.session() as session:
            query = select(ResumeProposalRow).order_by(ResumeProposalRow.id)
            if job_id is not None:
                query = query.where(ResumeProposalRow.job_id == job_id)
            rows = list(session.scalars(query).all())
            for row in rows:
                session.expunge(row)
            return rows

    def get_many(self, proposal_ids: list[str]) -> list[ResumeProposalRow]:
        rows = {row.id: row for row in self.list() if row.id in proposal_ids}
        return [rows[proposal_id] for proposal_id in proposal_ids if proposal_id in rows]

    def decide(self, proposal_id: str, decision: str) -> ResumeProposalRow | None:
        with self.database.session() as session:
            row = session.get(ResumeProposalRow, proposal_id)
            if row is None:
                return None
            if decision == "approve_current_job":
                row.status = ProposalStatus.APPROVED_CURRENT_JOB.value
                row.approved_job_id = row.job_id
            elif decision == "approve_fact_library":
                row.status = ProposalStatus.APPROVED_FACT_LIBRARY.value
                row.approved_job_id = None
            elif decision == "reject":
                row.status = ProposalStatus.REJECTED.value
                row.approved_job_id = None
            else:  # pragma: no cover - Pydantic rejects this
                raise ValueError(decision)
        return self.get(proposal_id)


class ResumeRecordRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def next_version(self, job_id: str) -> int:
        with self.database.session() as session:
            current = session.scalar(
                select(func.max(ResumeVersionRow.version)).where(ResumeVersionRow.job_id == job_id)
            )
            return int(current or 0) + 1

    def save(
        self,
        *,
        resume_id: str,
        job_id: str,
        version: int,
        template: str,
        content: dict,
        source_claim_ids: list[str],
        artifacts: list[dict],
    ) -> None:
        now = datetime.now(UTC)
        with self.database.session() as session:
            session.add(
                ResumeVersionRow(
                    id=resume_id,
                    job_id=job_id,
                    version=version,
                    template=template,
                    content_json=json.dumps(content, ensure_ascii=False),
                    source_claim_ids_json=json.dumps(source_claim_ids, ensure_ascii=False),
                    created_at=now,
                )
            )
            for artifact in artifacts:
                session.add(
                    ArtifactRow(
                        id=artifact["id"],
                        resume_version_id=resume_id,
                        format=artifact["format"],
                        path=artifact["path"],
                        sha256=artifact["sha256"],
                        created_at=now,
                    )
                )


def row_to_proposal(row: ResumeProposalRow) -> ResumeProposal:
    return ResumeProposal(
        id=row.id,
        kind=ProposalKind(row.kind),
        target_section=row.target_section,
        proposed_text=row.proposed_text,
        source_claim_ids=tuple(json.loads(row.source_claim_ids_json)),
        status=ProposalStatus(row.status),
    )


def proposal_payload(row: ResumeProposalRow) -> dict:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "kind": row.kind,
        "target_section": row.target_section,
        "proposed_text": row.proposed_text,
        "source_claim_ids": json.loads(row.source_claim_ids_json),
        "status": row.status,
        "approved_job_id": row.approved_job_id,
    }
