from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .fs_utils import sha1_file
from .scanner import scan_repository


@dataclass(slots=True)
class ScanStatus:
    is_stale: bool
    reasons: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)


EXPECTED_ARTIFACTS: tuple[str, ...] = (
    "index.md",
    "overview.md",
    "architecture.md",
    "routes.md",
    "schema.md",
    "components.md",
    "config.md",
    "hot-files.md",
    "map.json",
    "manifest.json",
)


def assess_scan_status(
    repo_root: Path,
    current_hashes: dict[str, str],
    compiler_version: str,
) -> ScanStatus:
    manifest_path = repo_root / ".context" / "manifest.json"
    if not manifest_path.exists():
        return ScanStatus(
            is_stale=True,
            reasons=["missing manifest"],
            missing_files=list(EXPECTED_ARTIFACTS),
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ScanStatus(is_stale=True, reasons=["unreadable manifest"])
    reasons: list[str] = []
    if manifest.get("compiler_version") != compiler_version:
        reasons.append("compiler-version mismatch")
    if manifest.get("source_hashes") != current_hashes:
        reasons.append("source-hash mismatch")
    expected_artifact_hashes = manifest.get("artifact_hashes")
    if isinstance(expected_artifact_hashes, dict) and expected_artifact_hashes:
        actual_artifact_hashes = _artifact_hashes(repo_root, manifest)
        if actual_artifact_hashes != expected_artifact_hashes:
            reasons.append("artifact-hash mismatch")
    missing: list[str] = []
    for name in EXPECTED_ARTIFACTS:
        if not (repo_root / ".context" / name).exists():
            missing.append(name)
    # Check for missing dynamic article files listed in manifest
    article_files = manifest.get("article_files", [])
    for name in article_files:
        if not (repo_root / ".context" / name).exists():
            missing.append(name)
    if missing:
        reasons.append("missing artifacts")
    # Check for orphan article files (exist on disk but not in manifest)
    context_dir = repo_root / ".context"
    if context_dir.exists():
        expected_files = set(EXPECTED_ARTIFACTS) | set(article_files)
        for path in context_dir.glob("*.md"):
            if path.name not in expected_files:
                reasons.append("orphan artifacts")
                break
    return ScanStatus(is_stale=bool(reasons), reasons=reasons, missing_files=missing)


def current_source_hashes(repo_root: Path) -> dict[str, str]:
    scan_input = scan_repository(repo_root)
    return {file.relative_path: file.sha1 for file in scan_input.files}


def rehash_file(path: Path) -> str:
    return sha1_file(path)


def _artifact_hashes(repo_root: Path, manifest: dict | None = None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    context_dir = repo_root / ".context"
    for name in EXPECTED_ARTIFACTS:
        if name == "manifest.json":
            continue
        path = context_dir / name
        if not path.exists():
            continue
        hashes[name] = hashlib.sha1(path.read_bytes()).hexdigest()
    # Include dynamic article files from manifest
    if manifest is not None:
        article_files = manifest.get("article_files", [])
        for name in article_files:
            path = context_dir / name
            if not path.exists():
                continue
            hashes[name] = hashlib.sha1(path.read_bytes()).hexdigest()
    return hashes
