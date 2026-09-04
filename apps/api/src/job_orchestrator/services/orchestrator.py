from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from job_orchestrator.domain.applications import (
    ApplicationStatus,
    ApplicationTask,
    AutomationMode,
)


@dataclass(frozen=True, slots=True)
class PreparedApplication:
    artifact_path: str
    artifact_sha256: str
    has_pending_claims: bool


@dataclass(frozen=True, slots=True)
class GatewayResult:
    status: Literal[
        "ready",
        "submitting",
        "submitted",
        "requires_user_action",
        "risk_stopped",
        "failed",
        "unknown",
    ]
    remote_id: str | None = None
    reason: str | None = None


class ResumePreparer(Protocol):
    def prepare(self, task: ApplicationTask, *, conservative: bool) -> PreparedApplication: ...


class PlatformGateway(Protocol):
    def preflight(
        self, task: ApplicationTask, prepared: PreparedApplication
    ) -> GatewayResult: ...

    def submit(self, task: ApplicationTask, prepared: PreparedApplication) -> GatewayResult: ...

    def observe_result(self, task: ApplicationTask) -> GatewayResult: ...


class ApplicationOrchestrator:
    def __init__(self, preparer: ResumePreparer, gateway: PlatformGateway) -> None:
        self.preparer = preparer
        self.gateway = gateway
        self._prepared: dict[str, PreparedApplication] = {}

    def process(self, task: ApplicationTask) -> ApplicationTask:
        if task.status in {
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.PREPARED,
            ApplicationStatus.FAILED,
            ApplicationStatus.RISK_STOPPED,
            ApplicationStatus.REQUIRES_USER_ACTION,
        }:
            return task
        if task.status is ApplicationStatus.SUBMITTING:
            self._apply_gateway_result(task, self.gateway.observe_result(task))
            return task

        if task.status is ApplicationStatus.QUEUED:
            task.transition(ApplicationStatus.PREPARING)
            conservative = task.mode is AutomationMode.AUTO_APPLY
            self._prepared[task.id] = self.preparer.prepare(task, conservative=conservative)

            if task.mode is AutomationMode.PREPARE_ONLY:
                task.transition(ApplicationStatus.PREPARED)
                return task
            if task.mode is AutomationMode.CONFIRM_BEFORE_APPLY:
                task.transition(ApplicationStatus.READY_FOR_CONFIRMATION)
                return task

        if task.status is ApplicationStatus.READY_FOR_CONFIRMATION and not task.approved:
            return task

        prepared = self._prepared.get(task.id)
        if prepared is None:
            prepared = self.preparer.prepare(
                task, conservative=task.mode is AutomationMode.AUTO_APPLY
            )
            self._prepared[task.id] = prepared
        self._submit(task, prepared)
        return task

    def _submit(self, task: ApplicationTask, prepared: PreparedApplication) -> None:
        preflight = self.gateway.preflight(task, prepared)
        if preflight.status != "ready":
            self._apply_preflight_failure(task, preflight)
            return
        task.transition(ApplicationStatus.SUBMITTING)
        self._apply_gateway_result(task, self.gateway.submit(task, prepared))

    def _apply_preflight_failure(self, task: ApplicationTask, result: GatewayResult) -> None:
        if result.status == "risk_stopped":
            task.risk_stop(result.reason or "platform_risk")
            return
        if result.status == "requires_user_action":
            # The state machine reaches user action through submitting so recovery stays explicit.
            task.transition(ApplicationStatus.SUBMITTING)
            task.transition(ApplicationStatus.REQUIRES_USER_ACTION)
            task.last_error = result.reason
            return
        task.transition(ApplicationStatus.FAILED)
        task.last_error = result.reason or "preflight_failed"

    def _apply_gateway_result(self, task: ApplicationTask, result: GatewayResult) -> None:
        if result.status == "submitted":
            task.transition(ApplicationStatus.SUBMITTED)
        elif result.status == "requires_user_action":
            task.transition(ApplicationStatus.REQUIRES_USER_ACTION)
            task.last_error = result.reason
        elif result.status == "risk_stopped":
            task.risk_stop(result.reason or "platform_risk")
        elif result.status == "failed":
            task.transition(ApplicationStatus.FAILED)
            task.last_error = result.reason or "submission_failed"
        # submitting/unknown deliberately remain submitting for observe_result recovery.

