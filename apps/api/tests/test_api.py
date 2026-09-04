from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from job_orchestrator.api.app import AppConfig, create_app


def client(tmp_path: Path) -> TestClient:
    config = AppConfig(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
    )
    return TestClient(create_app(config), base_url="http://127.0.0.1")


def test_health_and_default_presets(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        assert api.get("/api/health").json() == {"status": "ok", "version": "0.1.0"}
        presets = api.get("/api/screening/presets").json()

    assert presets["precise"]["minimum_score"] == 85
    assert presets["precise"]["daily_limit"] == 10


def test_screening_settings_default_and_custom_round_trip(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        defaults = api.get("/api/settings/screening")
        custom = defaults.json()
        custom["selected_preset"] = "custom"
        custom["automation_mode"] = "prepare_only"
        custom["profile"].update(
            {
                "name": "custom",
                "minimum_score": 76,
                "daily_limit": 12,
                "locations": ["深圳", "广州"],
                "salary_min_k": 20,
                "required_keywords": ["Python", "FastAPI"],
                "weights": {
                    "skills": 0.5,
                    "experience": 0.2,
                    "industry": 0.1,
                    "education": 0.05,
                    "preference": 0.15,
                },
            }
        )
        saved = api.put("/api/settings/screening", json=custom)
        reloaded = api.get("/api/settings/screening")

    assert defaults.status_code == 200
    assert defaults.json()["selected_preset"] == "precise"
    assert defaults.json()["automation_mode"] == "confirm_before_apply"
    assert saved.status_code == 200
    assert reloaded.json()["profile"]["minimum_score"] == 76
    assert reloaded.json()["profile"]["required_keywords"] == ["Python", "FastAPI"]


def test_claim_approval_and_job_specific_resume_artifacts(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        claim = api.post(
            "/api/claims",
            json={
                "id": "fact-fastapi",
                "category": "项目经历",
                "statement": "使用 FastAPI 构建本地服务",
                "evidence": "用户确认",
            },
        )
        safe = api.post(
            "/api/proposals",
            json={
                "id": "safe-1",
                "job_id": "boss-42",
                "kind": "safe_rewrite",
                "target_section": "项目经历",
                "proposed_text": "基于 FastAPI 交付本地编排服务",
                "source_claim_ids": ["fact-fastapi"],
            },
        )
        pending = api.post(
            "/api/proposals",
            json={
                "id": "pending-1",
                "job_id": "boss-42",
                "kind": "pending_claim",
                "target_section": "业绩",
                "proposed_text": "将处理效率提升 30%",
                "source_claim_ids": [],
            },
        )
        first = api.post(
            "/api/resumes/compose",
            json={
                "job_id": "boss-42",
                "base_sections": {"基本信息": ["张三 | Python 工程师"]},
                "proposal_ids": ["safe-1", "pending-1"],
                "conservative": True,
            },
        )
        decision = api.post(
            "/api/proposals/pending-1/decision",
            json={"decision": "approve_current_job"},
        )
        second = api.post(
            "/api/resumes/compose",
            json={
                "job_id": "boss-42",
                "base_sections": {"基本信息": ["张三 | Python 工程师"]},
                "proposal_ids": ["safe-1", "pending-1"],
                "conservative": False,
            },
        )

    assert claim.status_code == safe.status_code == pending.status_code == 201
    assert first.status_code == 201
    assert first.json()["included_proposal_ids"] == ["safe-1"]
    assert first.json()["excluded_proposal_ids"] == ["pending-1"]
    assert {item["format"] for item in first.json()["artifacts"]} == {"docx", "pdf"}
    assert decision.json()["status"] == "approved_current_job"
    assert second.json()["version"] == 2
    assert second.json()["included_proposal_ids"] == ["safe-1", "pending-1"]


def test_job_and_task_round_trip_with_manual_confirmation(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        job_response = api.post(
            "/api/jobs",
            json={
                "platform": "boss",
                "platform_job_id": "boss-99",
                "url": "https://www.zhipin.com/job_detail/boss-99.html",
                "company": "示例科技",
                "title": "Python 工程师",
                "description": "负责 FastAPI 服务",
                "salary_min_k": 18,
                "salary_max_k": 28,
                "location": "深圳",
                "experience": "3-5年",
                "education": "本科",
                "hr_active_at": "2026-08-18T01:00:00Z",
                "snapshot_at": "2026-08-18T02:00:00Z",
            },
        )
        assert job_response.status_code == 201

        task_response = api.post(
            "/api/tasks",
            json={
                "job_id": "boss-99",
                "resume_version_id": "resume-1",
                "greeting": "您好，我的经历与岗位要求匹配。",
                "mode": "confirm_before_apply",
                "platform": "boss",
            },
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]

        approve = api.post(f"/api/tasks/{task_id}/approve")
        listed = api.get("/api/tasks").json()

    assert approve.status_code == 200
    assert approve.json()["approved"] is True
    assert listed[0]["id"] == task_id


def test_pairing_api_does_not_reveal_platform_cookies(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        token = api.post("/api/pairing/token").json()["token"]
        paired = api.post(
            "/api/pairing/consume",
            headers={"Origin": "chrome-extension://abcdefghijklmnop"},
            json={"token": token},
        )

    assert paired.status_code == 200
    assert set(paired.json()) == {"session_token", "websocket_url"}
    assert "cookie" not in paired.text.casefold()


def test_paired_extension_websocket_registers_with_command_broker(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        token = api.post("/api/pairing/token").json()["token"]
        paired = api.post(
            "/api/pairing/consume",
            headers={"Origin": "chrome-extension://abcdefghijklmnop"},
            json={"token": token},
        ).json()
        websocket_path = "/ws/extension?session_token=" + paired["session_token"]
        with api.websocket_connect(
            websocket_path,
            headers={"Origin": "chrome-extension://abcdefghijklmnop"},
        ) as websocket:
            assert api.get("/api/extension/status").json()["connected"] is True
            websocket.send_json({"type": "heartbeat"})
            assert websocket.receive_json() == {"type": "heartbeat_ack"}

        assert api.get("/api/extension/status").json()["connected"] is False


def test_http_orchestrator_command_round_trips_through_extension(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        token = api.post("/api/pairing/token").json()["token"]
        session_token = api.post(
            "/api/pairing/consume",
            headers={"Origin": "chrome-extension://abcdefghijklmnop"},
            json={"token": token},
        ).json()["session_token"]
        with api.websocket_connect(
            f"/ws/extension?session_token={session_token}",
            headers={"Origin": "chrome-extension://abcdefghijklmnop"},
        ) as websocket:
            with ThreadPoolExecutor(max_workers=1) as pool:
                response_future = pool.submit(
                    api.post,
                    "/api/extension/commands",
                    json={"type": "detectPage", "payload": {}},
                )
                command = websocket.receive_json()
                websocket.send_json(
                    {"command_id": command["command_id"], "result": {"page": "job_detail"}}
                )
                response = response_future.result(timeout=3)

    assert command["type"] == "detectPage"
    assert response.status_code == 200
    assert response.json() == {"page": "job_detail"}


def test_non_loopback_host_is_rejected(tmp_path: Path) -> None:
    config = AppConfig(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
    )
    with TestClient(create_app(config), base_url="http://lan-machine") as api:
        response = api.get("/api/health")

    assert response.status_code == 403


def test_production_app_serves_built_web_dashboard(tmp_path: Path) -> None:
    web_root = tmp_path / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text("<h1>JobFlow dashboard</h1>", encoding="utf-8")
    config = AppConfig(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        web_root=web_root,
    )

    with TestClient(create_app(config), base_url="http://127.0.0.1") as api:
        response = api.get("/")

    assert response.status_code == 200
    assert "JobFlow dashboard" in response.text
