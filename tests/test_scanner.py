from pathlib import Path

from context_compiler.scanner import scan_repository


def test_scan_repository_collects_supported_files() -> None:
    repo = Path(__file__).parent / "fixtures" / "polyglot_repo"
    repo = repo.resolve()
    result = scan_repository(repo)
    rel_paths = {item.relative_path for item in result.files}
    assert "app/main.py" in rel_paths
    assert "web/src/index.ts" in rel_paths
    assert "api/main.go" in rel_paths
    assert ".git/config" not in rel_paths
    assert "app/settings.py" not in rel_paths


def test_scan_repository_caches_source_bytes_and_detects_spring_hints() -> None:
    repo = (Path(__file__).parent / "fixtures" / "deep_java_repo").resolve()
    result = scan_repository(repo)
    java_files = [item for item in result.files if item.language == "java"]
    assert java_files
    assert java_files[0].source_bytes
    assert "spring" in result.framework_hints.java
