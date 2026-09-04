from pathlib import Path


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("artifact path escapes the configured root")
    if not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate

