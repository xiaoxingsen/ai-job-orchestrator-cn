from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from docx import Document
from pypdf import PdfReader
from resume_engine.artifacts import ArtifactRenderer
from resume_engine.claims import (
    ApprovalScope,
    ApprovedClaim,
    ClaimLibrary,
    ProposalKind,
    ProposalStatus,
    ResumeProposal,
)
from resume_engine.composer import ResumeComposer


def claim(claim_id: str, statement: str) -> ApprovedClaim:
    return ApprovedClaim(
        id=claim_id,
        category="project",
        statement=statement,
        evidence="用户确认",
    )


def test_unapproved_content_never_enters_conservative_resume() -> None:
    library = ClaimLibrary([claim("fact-fastapi", "使用 FastAPI 构建本地服务")])
    proposals = [
        ResumeProposal(
            id="safe-1",
            kind=ProposalKind.SAFE_REWRITE,
            target_section="项目经历",
            proposed_text="基于 FastAPI 交付本地编排服务",
            source_claim_ids=("fact-fastapi",),
        ),
        ResumeProposal(
            id="invented-1",
            kind=ProposalKind.PENDING_CLAIM,
            target_section="项目经历",
            proposed_text="将转化率提升 50%",
        ),
    ]

    document = ResumeComposer(library).compose(
        job_id="boss-42",
        version=1,
        base_sections={"基本信息": ["张三 | Python 工程师"]},
        proposals=proposals,
        conservative=True,
    )

    assert "基于 FastAPI 交付本地编排服务" in document.plain_text
    assert "转化率提升 50%" not in document.plain_text
    assert document.excluded_proposal_ids == ("invented-1",)


def test_safe_rewrite_requires_approved_source_facts() -> None:
    library = ClaimLibrary()
    proposal = ResumeProposal(
        id="unsafe-rewrite",
        kind=ProposalKind.SAFE_REWRITE,
        target_section="技能",
        proposed_text="精通 Kubernetes",
        source_claim_ids=("missing-fact",),
    )

    document = ResumeComposer(library).compose(
        job_id="boss-42",
        version=1,
        base_sections={},
        proposals=[proposal],
        conservative=True,
    )

    assert "Kubernetes" not in document.plain_text
    assert document.excluded_proposal_ids == ("unsafe-rewrite",)


def test_pending_claim_can_be_approved_for_one_job_or_fact_library() -> None:
    library = ClaimLibrary()
    proposal = ResumeProposal(
        id="claim-1",
        kind=ProposalKind.PENDING_CLAIM,
        target_section="技能",
        proposed_text="熟悉 PostgreSQL 性能优化",
    )

    library.approve(proposal, ApprovalScope.CURRENT_JOB, job_id="boss-42")
    for_current_job = ResumeComposer(library).compose(
        job_id="boss-42", version=1, base_sections={}, proposals=[proposal]
    )
    for_other_job = ResumeComposer(library).compose(
        job_id="liepin-9", version=1, base_sections={}, proposals=[proposal]
    )

    assert proposal.status is ProposalStatus.APPROVED_CURRENT_JOB
    assert "PostgreSQL" in for_current_job.plain_text
    assert "PostgreSQL" not in for_other_job.plain_text

    library.approve(proposal, ApprovalScope.FACT_LIBRARY, job_id="boss-42")
    assert proposal.status is ProposalStatus.APPROVED_FACT_LIBRARY
    assert "PostgreSQL" in ResumeComposer(library).compose(
        job_id="liepin-9", version=2, base_sections={}, proposals=[proposal]
    ).plain_text


def test_rejected_claim_enters_negative_memory() -> None:
    library = ClaimLibrary()
    proposal = ResumeProposal(
        id="claim-2",
        kind=ProposalKind.PENDING_CLAIM,
        target_section="业绩",
        proposed_text="带领 10 人团队",
    )

    library.reject(proposal)

    assert proposal.status is ProposalStatus.REJECTED
    assert library.should_suggest("  带领10人团队。 ") is False


def test_docx_and_pdf_render_chinese_and_bind_hashes(tmp_path: Path) -> None:
    library = ClaimLibrary([claim("fact-1", "负责中文简历自动化")])
    proposal = ResumeProposal(
        id="safe-2",
        kind=ProposalKind.SAFE_REWRITE,
        target_section="项目经历",
        proposed_text="设计并实现中文简历自动化流程",
        source_claim_ids=("fact-1",),
    )
    resume = ResumeComposer(library).compose(
        job_id="boss-中文岗位",
        version=3,
        base_sections={"基本信息": ["张三 | 深圳 | Python 工程师"]},
        proposals=[proposal],
    )

    artifacts = ArtifactRenderer().render(resume, tmp_path)

    assert {item.format for item in artifacts} == {"docx", "pdf"}
    for item in artifacts:
        data = Path(item.path).read_bytes()
        assert item.sha256 == sha256(data).hexdigest()
        assert item.resume_version == 3
        assert item.job_id == "boss-中文岗位"

    docx = next(item for item in artifacts if item.format == "docx")
    pdf = next(item for item in artifacts if item.format == "pdf")
    docx_text = "\n".join(p.text for p in Document(docx.path).paragraphs)
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf.path).pages)

    assert "张三" in docx_text
    assert "中文简历自动化流程" in docx_text
    assert "张三" in pdf_text
    assert "中文简历自动化流程" in pdf_text

