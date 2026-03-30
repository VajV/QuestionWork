"""Shared enums/constants for trust-layer jobs."""

COMMAND_STATUS_ACCEPTED = "accepted"
COMMAND_STATUS_RUNNING = "running"
COMMAND_STATUS_SUCCEEDED = "succeeded"
COMMAND_STATUS_FAILED = "failed"
COMMAND_STATUS_CANCELLED = "cancelled"

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_RETRY_SCHEDULED = "retry_scheduled"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"
JOB_STATUS_DEAD_LETTER = "dead_letter"

QUEUE_DEFAULT = "default"
QUEUE_OPS = "ops"

RUNTIME_KIND_WORKER = "worker"
RUNTIME_KIND_SCHEDULER = "scheduler"
