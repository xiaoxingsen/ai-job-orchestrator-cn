from __future__ import annotations

import os
import sys
from pathlib import Path

from job_orchestrator.api.app import AppConfig, create_app


def _data_root() -> Path:
    configured = os.environ.get("JOBFLOW_DATA_ROOT")
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "JobFlowCN"
    return Path.cwd() / ".jobflow-data"


def _web_root() -> Path | None:
    configured = os.environ.get("JOBFLOW_WEB_ROOT")
    executable_root = (
        Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    )
    candidates = [
        Path(configured) if configured else None,
        Path(getattr(sys, "_MEIPASS", "")) / "web" if getattr(sys, "frozen", False) else None,
        executable_root / "_internal" / "web" if executable_root else None,
        executable_root / "web" if executable_root else None,
        Path.cwd() / "apps" / "web" / "dist",
        Path(__file__).resolve().parents[4] / "web",
    ]
    return next(
        (path for path in candidates if path is not None and (path / "index.html").is_file()),
        None,
    )


def create_runtime_app():
    data_root = _data_root()
    data_root.mkdir(parents=True, exist_ok=True)
    return create_app(
        AppConfig(
            database_url=f"sqlite:///{(data_root / 'jobflow.db').as_posix()}",
            artifact_root=data_root / "artifacts",
            web_root=_web_root(),
        )
    )


app = create_runtime_app()
