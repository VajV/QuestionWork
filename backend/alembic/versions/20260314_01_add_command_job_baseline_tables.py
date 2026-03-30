"""add command/job baseline tables

Revision ID: 20260314_01
Revises: b2c3d4e5f6a8
Create Date: 2026-03-14 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260314_01"
down_revision: Union[str, None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMMAND_STATUS_CHECK = "status IN ('accepted', 'running', 'succeeded', 'failed', 'cancelled')"
JOB_STATUS_CHECK = "status IN ('queued', 'running', 'succeeded', 'retry_scheduled', 'failed', 'cancelled', 'dead_letter')"
ATTEMPT_STATUS_CHECK = "status IN ('running', 'succeeded', 'retry_scheduled', 'failed', 'dead_letter')"


def upgrade() -> None:
    op.create_table(
        "command_requests",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("command_kind", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=50), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by_admin_id", sa.String(length=50), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_ip", postgresql.INET(), nullable=True),
        sa.Column("request_user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_check_constraint("chk_command_requests_status", "command_requests", COMMAND_STATUS_CHECK)
    op.create_index(
        "uq_command_requests_dedupe_active",
        "command_requests",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL AND status IN ('accepted', 'running')"),
    )
    op.create_index(
        "idx_command_requests_kind_submitted_at",
        "command_requests",
        ["command_kind", sa.text("submitted_at DESC")],
    )
    op.create_index(
        "idx_command_requests_admin_submitted_at",
        "command_requests",
        ["requested_by_admin_id", sa.text("submitted_at DESC")],
    )

    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("queue_name", sa.String(length=50), nullable=False, server_default=sa.text("'default'")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default=sa.text("100")),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_enqueue_error", sa.Text(), nullable=True),
        sa.Column("queue_publish_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("lock_token", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=50), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_admin_id", sa.String(length=50), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("command_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_check_constraint("chk_background_jobs_status", "background_jobs", JOB_STATUS_CHECK)
    op.create_check_constraint("chk_background_jobs_attempt_count_non_negative", "background_jobs", "attempt_count >= 0")
    op.create_check_constraint("chk_background_jobs_queue_publish_attempts_non_negative", "background_jobs", "queue_publish_attempts >= 0")
    op.create_check_constraint("chk_background_jobs_max_attempts_positive", "background_jobs", "max_attempts >= 1")
    op.create_index(
        "uq_background_jobs_dedupe_active",
        "background_jobs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL AND status IN ('queued', 'running', 'retry_scheduled')"),
    )
    op.create_index("idx_background_jobs_status_scheduled_for", "background_jobs", ["status", "scheduled_for"])
    op.create_index("idx_background_jobs_kind_status_scheduled_for", "background_jobs", ["kind", "status", "scheduled_for"])
    op.create_index("idx_background_jobs_command_id", "background_jobs", ["command_id"])

    op.create_table(
        "background_job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_background_job_attempts_job_attempt_no"),
    )
    op.create_check_constraint("chk_background_job_attempts_status", "background_job_attempts", ATTEMPT_STATUS_CHECK)
    op.create_index("idx_background_job_attempts_status_created_at", "background_job_attempts", ["status", "created_at"])

    op.create_table(
        "runtime_heartbeats",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("runtime_kind", sa.String(length=50), nullable=False),
        sa.Column("runtime_id", sa.String(length=255), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("runtime_kind", "runtime_id", name="uq_runtime_heartbeats_kind_runtime_id"),
    )
    op.create_index("idx_runtime_heartbeats_kind_last_seen", "runtime_heartbeats", ["runtime_kind", "last_seen_at"])

    op.add_column("admin_logs", sa.Column("command_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("admin_logs", sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("admin_logs", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("admin_logs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_admin_logs_command_id", "admin_logs", "command_requests", ["command_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_admin_logs_job_id", "admin_logs", "background_jobs", ["job_id"], ["id"], ondelete="SET NULL")

    op.add_column("email_outbox", sa.Column("command_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("email_outbox", sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("email_outbox", sa.Column("dedupe_key", sa.String(length=200), nullable=True))
    op.add_column("email_outbox", sa.Column("provider_message_id", sa.String(length=255), nullable=True))
    op.add_column("email_outbox", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_email_outbox_command_id", "email_outbox", "command_requests", ["command_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_email_outbox_job_id", "email_outbox", "background_jobs", ["job_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_email_outbox_job_id", "email_outbox", type_="foreignkey")
    op.drop_constraint("fk_email_outbox_command_id", "email_outbox", type_="foreignkey")
    op.drop_column("email_outbox", "next_attempt_at")
    op.drop_column("email_outbox", "last_attempt_at")
    op.drop_column("email_outbox", "provider_message_id")
    op.drop_column("email_outbox", "dedupe_key")
    op.drop_column("email_outbox", "job_id")
    op.drop_column("email_outbox", "command_id")

    op.drop_constraint("fk_admin_logs_job_id", "admin_logs", type_="foreignkey")
    op.drop_constraint("fk_admin_logs_command_id", "admin_logs", type_="foreignkey")
    op.drop_column("admin_logs", "trace_id")
    op.drop_column("admin_logs", "request_id")
    op.drop_column("admin_logs", "job_id")
    op.drop_column("admin_logs", "command_id")

    op.drop_index("idx_runtime_heartbeats_kind_last_seen", table_name="runtime_heartbeats")
    op.drop_table("runtime_heartbeats")

    op.drop_index("idx_background_job_attempts_status_created_at", table_name="background_job_attempts")
    op.drop_constraint("chk_background_job_attempts_status", "background_job_attempts", type_="check")
    op.drop_table("background_job_attempts")

    op.drop_index("idx_background_jobs_command_id", table_name="background_jobs")
    op.drop_index("idx_background_jobs_kind_status_scheduled_for", table_name="background_jobs")
    op.drop_index("idx_background_jobs_status_scheduled_for", table_name="background_jobs")
    op.drop_index("uq_background_jobs_dedupe_active", table_name="background_jobs")
    op.drop_constraint("chk_background_jobs_max_attempts_positive", "background_jobs", type_="check")
    op.drop_constraint("chk_background_jobs_queue_publish_attempts_non_negative", "background_jobs", type_="check")
    op.drop_constraint("chk_background_jobs_attempt_count_non_negative", "background_jobs", type_="check")
    op.drop_constraint("chk_background_jobs_status", "background_jobs", type_="check")
    op.drop_table("background_jobs")

    op.drop_index("idx_command_requests_admin_submitted_at", table_name="command_requests")
    op.drop_index("idx_command_requests_kind_submitted_at", table_name="command_requests")
    op.drop_index("uq_command_requests_dedupe_active", table_name="command_requests")
    op.drop_constraint("chk_command_requests_status", "command_requests", type_="check")
    op.drop_table("command_requests")