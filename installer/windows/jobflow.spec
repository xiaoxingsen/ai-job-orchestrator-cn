# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


root = Path(SPECPATH).parents[1]
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("resume_engine")
    + collect_submodules("job_orchestrator")
)

a = Analysis(
    [str(root / "apps" / "api" / "src" / "job_orchestrator" / "__main__.py")],
    pathex=[str(root / "apps" / "api" / "src"), str(root / "third_party" / "resume_engine" / "src")],
    binaries=[],
    datas=[
        (str(root / "apps" / "web" / "dist"), "web"),
        (str(root / "LICENSE"), "."),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
        (str(root / "third_party" / "resume_engine" / "LICENSE"), "resume_engine"),
    ],
    hiddenimports=hiddenimports,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JobFlowCN",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="JobFlowCN",
)
