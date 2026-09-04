from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar


class AutomationMode(StrEnum):
    CONFIRM_BEFORE_APPLY = "confirm_before_apply"
    AUTO_APPLY = "auto_apply"
    PREPARE_ONLY = "prepare_only"


class ApplicationStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    PREPARED = "prepared"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    REQUIRES_USER_ACTION = "requires_user_action"
    FAILED = "failed"
    RISK_STOPPED = "risk_stopped"


class RecoveryAction(StrEnum):
    CONTINUE = "continue"
    OBSERVE_RESULT = "observe_result"
    WAIT_FOR_USER = "wait_for_user"
    NONE = "none"


class InvalidTransition(ValueError):
    pass


_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.QUEUED: {ApplicationStatus.PREPARING},
    ApplicationStatus.PREPARING: {
        ApplicationStatus.READY_FOR_CONFIRMATION,
        ApplicationStatus.PREPARED,
        ApplicationStatus.SUBMITTING,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.READY_FOR_CONFIRMATION: {
        ApplicationStatus.SUBMITTING,
        ApplicationStatus.PREPARED,
    },
    ApplicationStatus.SUBMITTING: {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.REQUIRES_USER_ACTION,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.REQUIRES_USER_ACTION: {ApplicationStatus.SUBMITTED},
    ApplicationStatus.PREPARED: set(),
    ApplicationStatus.SUBMITTED: set(),
    ApplicationStatus.FAILED: set(),
    ApplicationStatus.RISK_STOPPED: set(),
}


@dataclass(slots=True)
class ApplicationTask:
    id: str
    job_id: str
    resume_version_id: str
    greeting: str
    mode: AutomationMode
    platform: str
    status: ApplicationStatus = ApplicationStatus.QUEUED
    approved: bool = False
    last_error: str | None = None
    history: list[ApplicationStatus] = field(default_factory=lambda: [ApplicationStatus.QUEUED])

    def transition(self, new_status: ApplicationStatus) -> None:
        if self.status is ApplicationStatus.RISK_STOPPED:
            raise InvalidTransition("risk-stopped tasks require a manual reset")
        if new_status is ApplicationStatus.SUBMITTING:
            if self.mode is AutomationMode.PREPARE_ONLY:
                raise InvalidTransition("prepare-only tasks cannot submit")
            if self.mode is AutomationMode.CONFIRM_BEFORE_APPLY and not self.approved:
                raise InvalidTransition("confirmation is required before submission")
        if new_status not in _TRANSITIONS[self.status]:
            raise InvalidTransition(f"cannot transition from {self.status} to {new_status}")
        self.status = new_status
        self.history.append(new_status)

    def approve(self) -> None:
        if self.status is not ApplicationStatus.READY_FOR_CONFIRMATION:
            raise InvalidTransition("only ready tasks can be approved")
        self.approved = True

    def risk_stop(self, reason: str) -> None:
        if self.status in {ApplicationStatus.SUBMITTED, ApplicationStatus.PREPARED}:
            raise InvalidTransition("completed tasks cannot be risk-stopped")
        self.status = ApplicationStatus.RISK_STOPPED
        self.last_error = reason
        self.history.append(ApplicationStatus.RISK_STOPPED)

    def manual_reset(self) -> None:
        if self.status is not ApplicationStatus.RISK_STOPPED:
            raise InvalidTransition("manual reset is only valid after a risk stop")
        self.status = ApplicationStatus.QUEUED
        self.last_error = None
        self.approved = False
        self.history.append(ApplicationStatus.QUEUED)

    def recovery_action(self) -> RecoveryAction:
        if self.status is ApplicationStatus.SUBMITTING:
            return RecoveryAction.OBSERVE_RESULT
        if self.status in {
            ApplicationStatus.READY_FOR_CONFIRMATION,
            ApplicationStatus.REQUIRES_USER_ACTION,
            ApplicationStatus.RISK_STOPPED,
        }:
            return RecoveryAction.WAIT_FOR_USER
        if self.status in {ApplicationStatus.SUBMITTED, ApplicationStatus.PREPARED}:
            return RecoveryAction.NONE
        return RecoveryAction.CONTINUE


T = TypeVar("T")


class CommandLedger:
    """In-memory command idempotency primitive; persistence is supplied by the repository layer."""

    def __init__(self) -> None:
        self._results: dict[str, object] = {}

    def execute(self, command_id: str, operation: Callable[[], T]) -> T:
        if command_id in self._results:
            return self._results[command_id]  # type: ignore[return-value]
        result = operation()
        self._results[command_id] = result
        return result

