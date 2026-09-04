from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from html import escape
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .composer import ResumeDocument


@dataclass(frozen=True, slots=True)
class Artifact:
    job_id: str
    resume_version: int
    format: str
    path: str
    sha256: str
    generated_at: datetime


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .-")
    return (cleaned or "job")[:80]


def _register_chinese_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for path in candidates:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("ResumeCJK", str(path), subfontIndex=0))
                return "ResumeCJK"
            except Exception:  # pragma: no cover - corrupted/system-specific font fallback
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


class ArtifactRenderer:
    def render(self, resume: ResumeDocument, output_dir: Path) -> tuple[Artifact, Artifact]:
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(UTC)
        docx_temp = output_dir / f".{_safe_name(resume.job_id)}-v{resume.version}.docx.building"
        pdf_temp = output_dir / f".{_safe_name(resume.job_id)}-v{resume.version}.pdf.building"
        self._render_docx(resume, docx_temp)
        self._render_pdf(resume, pdf_temp)
        return (
            self._finalize(resume, "docx", docx_temp, output_dir, generated_at),
            self._finalize(resume, "pdf", pdf_temp, output_dir, generated_at),
        )

    def _finalize(
        self,
        resume: ResumeDocument,
        artifact_format: str,
        temporary_path: Path,
        output_dir: Path,
        generated_at: datetime,
    ) -> Artifact:
        digest = sha256(temporary_path.read_bytes()).hexdigest()
        final_path = output_dir / (
            f"{_safe_name(resume.job_id)}-v{resume.version}-{digest[:12]}.{artifact_format}"
        )
        if final_path.exists():
            temporary_path.unlink()
        else:
            temporary_path.rename(final_path)
        return Artifact(
            job_id=resume.job_id,
            resume_version=resume.version,
            format=artifact_format,
            path=str(final_path.resolve()),
            sha256=digest,
            generated_at=generated_at,
        )

    def _render_docx(self, resume: ResumeDocument, path: Path) -> None:
        document = Document()
        normal = document.styles["Normal"]
        normal.font.name = "Microsoft YaHei"
        normal.font.size = Pt(10.5)
        normal._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        for heading, lines in resume.sections.items():
            document.add_heading(heading, level=1)
            for line in lines:
                document.add_paragraph(line)
        document.core_properties.title = f"岗位专属简历 - {resume.job_id}"
        document.core_properties.subject = f"Resume version {resume.version}"
        document.save(path)

    def _render_pdf(self, resume: ResumeDocument, path: Path) -> None:
        font_name = _register_chinese_font()
        styles = getSampleStyleSheet()
        heading = ParagraphStyle(
            "ResumeHeading",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=15,
            leading=20,
            spaceAfter=4 * mm,
            alignment=TA_LEFT,
        )
        body = ParagraphStyle(
            "ResumeBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            spaceAfter=2 * mm,
        )
        story = []
        for section_heading, lines in resume.sections.items():
            story.append(Paragraph(escape(section_heading), heading))
            for line in lines:
                story.append(Paragraph(escape(line), body))
            story.append(Spacer(1, 2 * mm))
        pdf = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"岗位专属简历 - {resume.job_id}",
            author="AI Job Orchestrator CN",
        )
        pdf.build(story)

