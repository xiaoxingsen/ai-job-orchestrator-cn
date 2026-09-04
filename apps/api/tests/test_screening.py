from datetime import UTC, datetime, timedelta

from job_orchestrator.domain.jobs import JobPosting, deduplicate_jobs
from job_orchestrator.domain.screening import PRESETS, ScreeningProfile, screen_job


def make_job(**overrides) -> JobPosting:
    values = {
        "platform": "boss",
        "platform_job_id": "job-1",
        "url": "https://www.zhipin.com/job_detail/job-1.html?ka=search_list_jname_1",
        "company": "示例科技",
        "title": "Python 后端工程师",
        "description": "负责 FastAPI 服务与 SQLite 数据建模",
        "salary_min_k": 20,
        "salary_max_k": 30,
        "location": "深圳",
        "experience": "3-5年",
        "education": "本科",
        "hr_active_at": datetime.now(UTC) - timedelta(days=2),
        "snapshot_at": datetime.now(UTC),
    }
    values.update(overrides)
    return JobPosting(**values)


def test_presets_match_product_defaults() -> None:
    assert PRESETS["precise"].minimum_score == 85
    assert PRESETS["precise"].hr_active_within_days == 7
    assert PRESETS["precise"].daily_limit == 10
    assert PRESETS["balanced"].minimum_score == 70
    assert PRESETS["balanced"].hr_active_within_days == 30
    assert PRESETS["balanced"].daily_limit == 20
    assert PRESETS["broad"].minimum_score == 55
    assert PRESETS["broad"].hr_active_within_days is None
    assert PRESETS["broad"].daily_limit == 30


def test_hard_filters_run_before_ai_score() -> None:
    profile = ScreeningProfile(
        name="custom",
        minimum_score=70,
        daily_limit=15,
        locations={"深圳"},
        salary_min_k=18,
        excluded_companies={"外包公司"},
        required_keywords={"Python"},
        excluded_keywords={"销售"},
        hr_active_within_days=7,
    )

    accepted = screen_job(make_job(), profile, ai_score=88)
    rejected = screen_job(make_job(location="广州"), profile, ai_score=99)

    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.ai_evaluated is False
    assert rejected.reasons == ["location_not_allowed"]


def test_ai_score_is_applied_after_hard_filters() -> None:
    result = screen_job(make_job(), PRESETS["balanced"], ai_score=69)
    assert result.accepted is False
    assert result.ai_evaluated is True
    assert result.reasons == ["score_below_threshold"]


def test_job_deduplication_uses_platform_id_then_canonical_url() -> None:
    original = make_job()
    newer_duplicate = make_job(
        url="https://www.zhipin.com/job_detail/job-1.html?from=chat",
        snapshot_at=original.snapshot_at + timedelta(minutes=5),
        description="更新后的 JD",
    )
    same_url_without_id = make_job(
        platform="liepin",
        platform_job_id="",
        url="https://www.liepin.com/job/123/?foo=bar",
    )
    same_url_again = make_job(
        platform="liepin",
        platform_job_id="",
        url="https://www.liepin.com/job/123/?utm_source=test",
        snapshot_at=same_url_without_id.snapshot_at + timedelta(minutes=1),
    )

    result = deduplicate_jobs([original, newer_duplicate, same_url_without_id, same_url_again])

    assert len(result) == 2
    assert result[0].description == "更新后的 JD"
    assert result[1].snapshot_at == same_url_again.snapshot_at

