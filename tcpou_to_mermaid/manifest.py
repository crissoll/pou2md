from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from collections.abc import Iterable
from pathlib import Path

MANIFEST_NAME = ".pou2md-manifest.json"


def manifest_path(output: str | Path) -> Path:
    target = Path(output)
    return target.parent / MANIFEST_NAME if target.suffix.lower() == ".md" else target / MANIFEST_NAME


def load_manifest(path: Path) -> set[Path]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        root = path.parent.resolve()
        outputs = set()
        for item in data.get("outputs", []):
            candidate = (path.parent / Path(item)).resolve()
            if candidate == root or root in candidate.parents:
                outputs.add(candidate)
        return outputs
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return set()


def save_manifest(
    path: Path,
    outputs: Iterable[Path],
    dry_run: bool = False,
    metadata: dict[str, object] | None = None,
) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    root = path.parent.resolve()
    relative_outputs = sorted(
        str(output.resolve().relative_to(root))
        for output in outputs
        if output.resolve() != path.resolve() and root in output.resolve().parents
    )
    payload = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outputs": relative_outputs,
        "metadata": metadata or {},
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_stale_outputs(manifest: Path, current_outputs: set[Path], dry_run: bool = False) -> list[Path]:
    stale = sorted(load_manifest(manifest) - current_outputs)
    if not dry_run:
        for output in stale:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                continue
        save_manifest(manifest, current_outputs)
        for parent in sorted({output.parent for output in stale}, reverse=True):
            try:
                parent.rmdir()
            except OSError:
                pass
    return stale
