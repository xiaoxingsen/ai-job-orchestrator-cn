from uuid import uuid4

import pytest
from job_orchestrator.domain.applications import (
    ApplicationStatus,
    ApplicationTask,
    AutomationMode,
    CommandLedger,
    InvalidTransition,
    RecoveryAction,
)


def task(mode: AutomationMode = AutomationMode.CONFIRM_BEFORE_APPLY) -> ApplicationTask:
    return ApplicationTask(
        id=str(uuid4()),
        job_id="job-1",
        resume_version_id="resume-1",
        greeting="您好，我的经历与岗位要求匹配，期待沟通。",
        mode=mode,
        platform="boss",
    )


def test_all_three_automation_modes_are_domain_values() -> None:
    assert {mode.value for mode in AutomationMode} == {
        "confirm_before_apply",
        "auto_apply",
        "prepare_only",
    }


def test_confirm_mode_waits_for_explicit_approval() -> None:
    application = task()
    application.transition(ApplicationStatus.PREPARING)
    application.transition(ApplicationStatus.READY_FOR_CONFIRMATION)

    with pytest.raises(InvalidTransition):
        application.transition(ApplicationStatus.SUBMITTING)

    application.approve()
    application.transition(ApplicationStatus.SUBMITTING)
    assert application.status is ApplicationStatus.SUBMITTING


def test_prepare_only_cannot_submit() -> None:
    application = task(AutomationMode.PREPARE_ONLY)
    application.transition(ApplicationStatus.PREPARING)
    application.transition(ApplicationStatus.PREPARED)

    with pytest.raises(InvalidTransition):
        application.transition(ApplicationStatus.SUBMITTING)


def test_duplicate_command_returns_original_result() -> None:
    ledger = CommandLedger()
    calls = 0

    def submit() -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "submitted", "remote_id": "chat-42"}

    command_id = str(uuid4())
    first = ledger.execute(command_id, submit)
    second = ledger.execute(command_id, submit)

    assert first == second
    assert calls == 1


def test_interrupted_submission_must_observe_before_retry() -> None:
    application = task(AutomationMode.AUTO_APPLY)
    application.status = ApplicationStatus.SUBMITTING
    assert application.recovery_action() is RecoveryAction.OBSERVE_RESULT


def test_risk_stop_is_terminal_until_manual_reset() -> None:
    application = task(AutomationMode.AUTO_APPLY)
    application.transition(ApplicationStatus.PREPARING)
    application.risk_stop("captcha_detected")

    assert application.status is ApplicationStatus.RISK_STOPPED
    assert application.last_error == "captcha_detected"
    with pytest.raises(InvalidTransition):
        application.transition(ApplicationStatus.PREPARING)

    application.manual_reset()
    assert application.status is ApplicationStatus.QUEUED

