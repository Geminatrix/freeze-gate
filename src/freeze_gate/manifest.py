"""Freeze manifest construction and I/O.

A freeze manifest is the single source of truth for a frozen core: what is in
it (artifact digests), where it came from (provenance), and what it honestly
claims to be (labeling). See docs/SPEC.md for the normative field definitions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_VERSION = "1.0"
MANIFEST_FILENAME = "freeze-manifest.json"

# Labeling fields a manifest must carry to count as honestly labeled.
# Empty `modifications` is a valid "none" claim; only a missing/null value is unlabeled.
REQUIRED_LABEL_FIELDS = ("base_model", "modifications", "intended_use")

_CHUNK_SIZE = 1 << 20  # 1 MiB


def hash_file(path: Path) -> str:
    """Return the sha256 hex digest of a file, streamed in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_core_files(core_dir: Path):
    """Yield every regular file under core_dir, excluding the manifest itself."""
    for path in sorted(core_dir.rglob("*")):
        if path.is_file() and path.name != MANIFEST_FILENAME:
            yield path


def build_manifest(
    core_dir: Path,
    core_id: str,
    core_version: str,
    labeling: dict,
    parent_core: str | None = None,
    frozen_by: str | None = None,
) -> dict:
    """Walk core_dir and build a freeze manifest dict for its current contents.

    Raises ValueError if the directory is empty — an empty core cannot be
    meaningfully frozen or verified.
    """
    core_dir = Path(core_dir)
    if not core_dir.is_dir():
        raise ValueError(f"{core_dir} is not a directory")
    artifacts = [
        {
            "path": path.relative_to(core_dir).as_posix(),
            "sha256": hash_file(path),
            "bytes": path.stat().st_size,
        }
        for path in _iter_core_files(core_dir)
    ]
    if not artifacts:
        raise ValueError(f"no artifacts found under {core_dir}; refusing to freeze an empty core")

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "core": {
            "id": core_id,
            "version": core_version,
            "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "labeling": dict(labeling),
        "provenance": {
            "parent_core": parent_core,
            "frozen_by": frozen_by,
        },
        "artifacts": artifacts,
    }
    return manifest


def write_manifest(manifest: dict, core_dir: Path) -> Path:
    """Write the manifest into core_dir as freeze-manifest.json and return its path."""
    out_path = Path(core_dir) / MANIFEST_FILENAME
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n")
    return out_path


def load_manifest(path: Path) -> dict:
    """Load a manifest from a JSON file. Accepts the file or its containing dir."""
    path = Path(path)
    if path.is_dir():
        path = path / MANIFEST_FILENAME
    with open(path) as fh:
        return json.load(fh)
