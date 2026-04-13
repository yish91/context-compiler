from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .models import CompiledProject

ARTIFACT_FILES: tuple[tuple[str, str], ...] = (
    ("index.md", "index"),
    ("overview.md", "overview"),
    ("architecture.md", "architecture"),
    ("routes.md", "routes"),
    ("schema.md", "schema"),
    ("components.md", "components"),
    ("config.md", "config"),
    ("hot-files.md", "hot_files_markdown"),
)


def _read_previous_article_files(context_dir: Path) -> list[str]:
    """Read the list of article files from the previous manifest."""
    manifest_path = context_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest.get("article_files", [])
    except (json.JSONDecodeError, OSError):
        return []


def _cleanup_orphan_articles(context_dir: Path, old_files: list[str], new_files: list[str]) -> None:
    """Delete article files that existed before but are no longer generated.

    Also removes any unexpected .md files that aren't in the expected static
    artifact set or the new article list - this handles orphans from before
    article_files tracking was added.
    """
    # Static artifacts that should never be cleaned up
    static_artifacts = {name for name, _ in ARTIFACT_FILES}

    new_set = set(new_files)

    # Remove files from previous manifest that aren't in new list
    for filename in old_files:
        if filename not in new_set:
            orphan_path = context_dir / filename
            if orphan_path.exists():
                orphan_path.unlink()

    # Also scan for any unexpected .md files (handles pre-tracking orphans)
    expected_files = static_artifacts | new_set
    for path in context_dir.glob("*.md"):
        if path.name not in expected_files:
            path.unlink()


def write_artifacts(repo_root: Path, compiled: CompiledProject) -> Path:
    context_dir = repo_root / ".context"
    context_dir.mkdir(parents=True, exist_ok=True)

    # Read previous article files before writing new ones
    previous_article_files = _read_previous_article_files(context_dir)

    artifact_hashes: dict[str, str] = {}
    for filename, attr in ARTIFACT_FILES:
        content = getattr(compiled, attr)
        path = context_dir / filename
        path.write_text(content, encoding="utf-8")
        artifact_hashes[filename] = hashlib.sha1(content.encode("utf-8")).hexdigest()
    map_text = json.dumps(compiled.map_json, indent=2, sort_keys=True)
    (context_dir / "map.json").write_text(map_text, encoding="utf-8")
    artifact_hashes["map.json"] = hashlib.sha1(map_text.encode("utf-8")).hexdigest()
    # Write dynamic article files
    article_files: list[str] = []
    for article in compiled.articles:
        filename = f"{article.name}.md"
        path = context_dir / filename
        path.write_text(article.markdown, encoding="utf-8")
        artifact_hashes[filename] = hashlib.sha1(article.markdown.encode("utf-8")).hexdigest()
        article_files.append(filename)

    # Clean up orphan article files from previous scans
    _cleanup_orphan_articles(context_dir, previous_article_files, article_files)

    manifest = {
        "compiler_version": compiled.compiler_version,
        "scan_time": int(time.time()),
        "source_hashes": {file.relative_path: file.sha1 for file in compiled.files},
        "artifact_hashes": artifact_hashes,
        "article_files": article_files,
    }
    (context_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return context_dir
