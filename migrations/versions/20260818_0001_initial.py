"""Initial local-first job orchestration schema."""

import sqlalchemy as sa
from alembic import op

revision = "20260818_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_job_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("salary_min_k", sa.Integer()),
        sa.Column("salary_max_k", sa.Integer()),
        sa.Column("location", sa.String(100), nullable=False),
        sa.Column("experience", sa.String(100), nullable=False),
        sa.Column("education", sa.String(100), nullable=False),
        sa.Column("hr_active_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("platform", "platform_job_id"),
    )
    op.create_index("ix_job_postings_platform", "job_postings", ["platform"])
    op.create_index("ix_job_postings_platform_job_id", "job_postings", ["platform_job_id"])
    op.create_index("ix_job_postings_snapshot_at", "job_postings", ["snapshot_at"])

    op.create_table(
        "approved_claims",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "resume_proposals",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("job_id", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("target_section", sa.String(100), nullable=False),
        sa.Column("proposed_text", sa.Text(), nullable=False),
        sa.Column("source_claim_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("approved_job_id", sa.String(255)),
    )
    op.create_index("ix_resume_proposals_job_id", "resume_proposals", ["job_id"])
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("job_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(100), nullable=False, server_default="default-cn"),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("source_claim_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "version"),
    )
    op.create_index("ix_resume_versions_job_id", "resume_versions", ["job_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("resume_version_id", sa.String(255), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_resume_version_id", "artifacts", ["resume_version_id"])
    op.create_table(
        "application_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(255), nullable=False),
        sa.Column("resume_version_id", sa.String(255), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_error", sa.Text()),
        sa.Column("history_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("job_id", "mode", "platform", "status"):
        op.create_index(f"ix_application_tasks_{column}", "application_tasks", [column])
    op.create_table(
        "command_ledger",
        sa.Column("command_id", sa.String(64), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_command_ledger_platform", "command_ledger", ["platform"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255)),
        sa.Column("redacted_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_event", "audit_log", ["event"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value_json", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "settings",
        "audit_log",
        "command_ledger",
        "application_tasks",
        "artifacts",
        "resume_versions",
        "resume_proposals",
        "approved_claims",
        "job_postings",
    ):
        op.drop_table(table)

