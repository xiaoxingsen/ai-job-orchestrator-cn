import os
import sys

import uvicorn


def _ensure_standard_streams() -> None:
    """Provide writable streams for Windows GUI executables.

    PyInstaller's windowed bootloader sets these streams to ``None``. Uvicorn's
    logging setup expects file-like objects even when no console is visible.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def main() -> None:
    _ensure_standard_streams()
    if os.name == "nt" and os.environ.get("JOBFLOW_NO_TRAY") != "1":
        try:
            from job_orchestrator.tray import TrayApplication

            TrayApplication().run()
            return
        except ImportError:
            pass
    uvicorn.run(
        "job_orchestrator.runtime:app",
        host="127.0.0.1",
        port=8765,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
