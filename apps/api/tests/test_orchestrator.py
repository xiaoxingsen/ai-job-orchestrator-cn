from dataclasses import dataclass

from job_orchestrator.domain.applications import ApplicationStatus, ApplicationTask, AutomationMode
from job_orchestrator.services.orchestrator import (
    ApplicationOrchestrator,
    GatewayResult,
    PreparedApplication,
)


@dataclass
class FakePreparer:
    pending_claims: bool = True
    calls: list[bool] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def prepare(self, task: ApplicationTask, *, conservative: bool) -> PreparedApplication:
        assert self.calls is not None
        self.calls.append(conservative)
        return PreparedApplication(
            artifact_path=f"artifacts/{task.id}.pdf",
            artifact_sha256="a" * 64,
            has_pending_claims=self.pending_claims,
        )


class FakeGateway:
    def __init__(self, result: GatewayResult | None = None) -> None:
        self.result = result or GatewayResult(status="submitted", remote_id="chat-1")
        self.submit_calls = 0
        self.observe_calls = 0

    def preflight(self, task: ApplicationTask, prepared: PreparedApplication) -> GatewayResult:
        return GatewayResult(status="ready")

    def submit(self, task: ApplicationTask, prepared: PreparedApplication) -> GatewayResult:
        self.submit_calls += 1
        return self.result

    def observe_result(self, task: ApplicationTask) -> GatewayResult:
        self.observe_calls += 1
        return self.result


def task(mode: AutomationMode) -> ApplicationTask:
    return ApplicationTask(
        id=f"task-{mode.value}",
        job_id="boss-1",
        resume_version_id="resume-1",
        greeting="您好，期待沟通。",
        mode=mode,
        platform="boss",
    )


def test_prepare_only_generates_artifact_without_submitting() -> None:
    preparer = FakePreparer()
    gateway = FakeGateway()
    item = task(AutomationMode.PREPARE_ONLY)

    ApplicationOrchestrator(preparer, gateway).process(item)

    assert item.status is ApplicationStatus.PREPARED
    assert gateway.submit_calls == 0


def test_confirmation_mode_waits_then_submits_after_approval() -> None:
    preparer = FakePreparer(pending_claims=False)
    gateway = FakeGateway()
    orchestrator = ApplicationOrchestrator(preparer, gateway)
    item = task(AutomationMode.CONFIRM_BEFORE_APPLY)

    orchestrator.process(item)
    assert item.status is ApplicationStatus.READY_FOR_CONFIRMATION
    assert gateway.submit_calls == 0

    item.approve()
    orchestrator.process(item)
    assert item.status is ApplicationStatus.SUBMITTED
    assert gateway.submit_calls == 1


def test_auto_mode_uses_conservative_resume_and_does_not_pause_for_pending_claims() -> None:
    preparer = FakePreparer(pending_claims=True)
    gateway = FakeGateway()
    item = task(AutomationMode.AUTO_APPLY)

    ApplicationOrchestrator(preparer, gateway).process(item)

    assert preparer.calls == [True]
    assert item.status is ApplicationStatus.SUBMITTED
    assert gateway.submit_calls == 1


def test_attachment_block_enters_requires_user_action() -> None:
    gateway = FakeGateway(GatewayResult(status="requires_user_action", reason="attachment_blocked"))
    item = task(AutomationMode.AUTO_APPLY)

    ApplicationOrchestrator(FakePreparer(), gateway).process(item)

    assert item.status is ApplicationStatus.REQUIRES_USER_ACTION
    assert item.last_error == "attachment_blocked"


def test_captcha_enters_risk_stop_without_retry() -> None:
    gateway = FakeGateway(GatewayResult(status="risk_stopped", reason="captcha_detected"))
    item = task(AutomationMode.AUTO_APPLY)

    orchestrator = ApplicationOrchestrator(FakePreparer(), gateway)
    orchestrator.process(item)
    orchestrator.process(item)

    assert item.status is ApplicationStatus.RISK_STOPPED
    assert item.last_error == "captcha_detected"
    assert gateway.submit_calls == 1


def test_recovered_submitting_task_observes_instead_of_resubmitting() -> None:
    gateway = FakeGateway(GatewayResult(status="submitted", remote_id="chat-recovered"))
    item = task(AutomationMode.AUTO_APPLY)
    item.status = ApplicationStatus.SUBMITTING

    ApplicationOrchestrator(FakePreparer(), gateway).process(item)

    assert item.status is ApplicationStatus.SUBMITTED
    assert gateway.observe_calls == 1
    assert gateway.submit_calls == 0

