from __future__ import annotations

import os
import shutil
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import pystray
import uvicorn
from PIL import Image, ImageDraw

from job_orchestrator.runtime import _data_root

DASHBOARD_URL = "http://127.0.0.1:8765"


def _icon() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#1565d8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=14, fill="#1565d8")
    draw.line((22, 18, 42, 18, 42, 42, 28, 48, 20, 40), fill="white", width=6, joint="curve")
    return image


class TrayApplication:
    def __init__(self) -> None:
        config = uvicorn.Config(
            "job_orchestrator.runtime:app",
            host="127.0.0.1",
            port=8765,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(
            target=self.server.run,
            name="jobflow-api",
            daemon=True,
        )
        self.icon = pystray.Icon(
            "jobflow-cn",
            _icon(),
            "JobFlow CN",
            menu=pystray.Menu(
                pystray.MenuItem("打开工作台", self.open_dashboard, default=True),
                pystray.MenuItem("备份数据库", self.backup_database),
                pystray.MenuItem("退出", self.exit),
            ),
        )

    def run(self) -> None:
        self.server_thread.start()
        threading.Timer(1.2, self.open_dashboard).start()
        self.icon.run()

    def open_dashboard(self, *_args) -> None:
        webbrowser.open(DASHBOARD_URL)

    def backup_database(self, *_args) -> None:
        source = _data_root() / "jobflow.db"
        if not source.is_file():
            return
        documents = Path(os.environ.get("USERPROFILE", str(_data_root()))) / "Documents"
        backup_dir = documents / "JobFlowCN-Backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(source, backup_dir / f"jobflow-{stamp}.db")

    def exit(self, *_args) -> None:
        self.server.should_exit = True
        self.icon.stop()
