import hashlib
from pathlib import Path

from typer.testing import CliRunner

from context_compiler.cli import app
from context_compiler.freshness import assess_scan_status

runner = CliRunner()


def test_assess_scan_status_reports_source_or_version_drift(tmp_path: Path) -> None:
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        '"artifact_hashes": {"index.md": "1"}, "scan_time": 0}',
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "def"}, compiler_version="0.1.1")
    assert status.is_stale is True
    assert "source-hash mismatch" in status.reasons
    assert "compiler-version mismatch" in status.reasons


def test_assess_scan_status_missing_manifest_is_stale(tmp_path: Path) -> None:
    status = assess_scan_status(tmp_path, {}, compiler_version="0.1.0")
    assert status.is_stale is True
    assert "missing manifest" in status.reasons


def test_assess_scan_status_clean_when_hashes_match(tmp_path: Path) -> None:
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    artifact_hashes = {}
    for name in (
        "index.md",
        "overview.md",
        "architecture.md",
        "routes.md",
        "schema.md",
        "components.md",
        "config.md",
        "hot-files.md",
        "map.json",
    ):
        (context_dir / name).write_text("stub", encoding="utf-8")
        artifact_hashes[name] = hashlib.sha1(b"stub").hexdigest()
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        f'"artifact_hashes": {artifact_hashes!r}, "scan_time": 0}}'.replace("'", '"'),
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "abc"}, compiler_version="0.1.0")
    assert status.is_stale is False
    assert status.reasons == []


def test_assess_scan_status_reports_artifact_hash_drift(tmp_path: Path) -> None:
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    artifact_hashes = {}
    for name in (
        "index.md",
        "overview.md",
        "architecture.md",
        "routes.md",
        "schema.md",
        "components.md",
        "config.md",
        "hot-files.md",
        "map.json",
    ):
        (context_dir / name).write_text("original", encoding="utf-8")
        artifact_hashes[name] = hashlib.sha1(b"original").hexdigest()
    (context_dir / "index.md").write_text("mutated", encoding="utf-8")
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        f'"artifact_hashes": {artifact_hashes!r}, "scan_time": 0}}'.replace("'", '"'),
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "abc"}, compiler_version="0.1.0")
    assert status.is_stale is True
    assert "artifact-hash mismatch" in status.reasons


def test_doctor_cli_reports_missing_setup(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", str(tmp_path)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower() or "missing" in result.output.lower()


def test_doctor_cli_reports_clean_after_scan(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    assert runner.invoke(app, ["scan", str(tmp_path)]).exit_code == 0
    result = runner.invoke(app, ["doctor", str(tmp_path)])
    assert result.exit_code == 0
    assert "ok" in result.output.lower()


def test_assess_scan_status_reports_missing_article_file(tmp_path: Path) -> None:
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    artifact_hashes = {}
    for name in (
        "index.md",
        "overview.md",
        "architecture.md",
        "routes.md",
        "schema.md",
        "components.md",
        "config.md",
        "hot-files.md",
        "map.json",
    ):
        (context_dir / name).write_text("stub", encoding="utf-8")
        artifact_hashes[name] = hashlib.sha1(b"stub").hexdigest()
    # Add an article file to the manifest but don't create the file
    artifact_hashes["subsystem-api.md"] = hashlib.sha1(b"# API\n").hexdigest()
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        f'"artifact_hashes": {artifact_hashes!r}, "article_files": ["subsystem-api.md"], "scan_time": 0}}'.replace("'", '"'),
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "abc"}, compiler_version="0.1.0")
    assert status.is_stale is True
    assert "missing artifacts" in status.reasons
    assert "subsystem-api.md" in status.missing_files


def test_assess_scan_status_clean_with_article_files(tmp_path: Path) -> None:
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    artifact_hashes = {}
    for name in (
        "index.md",
        "overview.md",
        "architecture.md",
        "routes.md",
        "schema.md",
        "components.md",
        "config.md",
        "hot-files.md",
        "map.json",
    ):
        (context_dir / name).write_text("stub", encoding="utf-8")
        artifact_hashes[name] = hashlib.sha1(b"stub").hexdigest()
    # Add an article file to the manifest and create the file
    (context_dir / "subsystem-api.md").write_text("# API\n", encoding="utf-8")
    artifact_hashes["subsystem-api.md"] = hashlib.sha1(b"# API\n").hexdigest()
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        f'"artifact_hashes": {artifact_hashes!r}, "article_files": ["subsystem-api.md"], "scan_time": 0}}'.replace("'", '"'),
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "abc"}, compiler_version="0.1.0")
    assert status.is_stale is False
    assert status.reasons == []


def test_assess_scan_status_reports_orphan_article_file(tmp_path: Path) -> None:
    """Test that orphan .md files not in manifest are detected as stale."""
    context_dir = tmp_path / ".context"
    context_dir.mkdir()
    artifact_hashes = {}
    for name in (
        "index.md",
        "overview.md",
        "architecture.md",
        "routes.md",
        "schema.md",
        "components.md",
        "config.md",
        "hot-files.md",
        "map.json",
    ):
        (context_dir / name).write_text("stub", encoding="utf-8")
        artifact_hashes[name] = hashlib.sha1(b"stub").hexdigest()
    # Create an orphan article file that's NOT in the manifest
    (context_dir / "domain-old.md").write_text("# Old Domain\n", encoding="utf-8")
    (context_dir / "manifest.json").write_text(
        '{"compiler_version": "0.1.0", "source_hashes": {"app.py": "abc"}, '
        f'"artifact_hashes": {artifact_hashes!r}, "article_files": [], "scan_time": 0}}'.replace("'", '"'),
        encoding="utf-8",
    )
    status = assess_scan_status(tmp_path, {"app.py": "abc"}, compiler_version="0.1.0")
    assert status.is_stale is True
    assert "orphan artifacts" in status.reasons
