import sys
from pathlib import Path

from job_orchestrator import __main__ as application_main


def test_pyinstaller_collects_application_runtime_modules() -> None:
    project_root = Path(__file__).resolve().parents[3]
    spec = (project_root / "installer" / "windows" / "jobflow.spec").read_text(
        encoding="utf-8"
    )

    assert 'collect_submodules("job_orchestrator")' in spec


def test_windowed_entrypoint_restores_missing_standard_streams(monkeypatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", None)
        patch.setattr(sys, "stderr", None)

        application_main._ensure_standard_streams()

        assert sys.stdout is not None
        assert sys.stderr is not None
        sys.stdout.close()
        sys.stderr.close()


def test_web_root_falls_back_to_packaged_internal_directory(
    monkeypatch, tmp_path: Path
) -> None:
    packaged_web = tmp_path / "_internal" / "web"
    packaged_web.mkdir(parents=True)
    (packaged_web / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setenv("JOBFLOW_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.delenv("JOBFLOW_WEB_ROOT", raising=False)

    from job_orchestrator import runtime

    monkeypatch.setattr(sys, "executable", str(tmp_path / "JobFlowCN.exe"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing"), raising=False)

    assert runtime._web_root() == packaged_web
