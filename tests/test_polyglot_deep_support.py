from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.language_packs.shared import merge_records
from context_compiler.models import Endpoint
from context_compiler.scanner import scan_repository


def test_merge_records_keeps_the_richer_row_for_the_same_endpoint_identity() -> None:
    baseline = Endpoint("GET", "/users", "usersHandler", "src/routes.ts", 9, "express")
    deep = Endpoint("GET", "/users", "", "src/routes.ts", 9, "typescript-express")
    merged = merge_records(
        [baseline],
        [deep],
        key=lambda item: (item.source_path, item.line, item.method, item.path),
    )
    assert len(merged) == 1
    assert merged[0].handler == "usersHandler"
    assert merged[0].framework == "typescript-express"


def test_polyglot_repo_runs_all_phase1_packs_without_duplicate_routes() -> None:
    repo = (Path(__file__).parent / "fixtures" / "polyglot_repo").resolve()
    project = extract_project(scan_repository(repo))
    frameworks = {item.framework for item in project.entrypoints}
    assert {"typescript-generic", "python-generic", "go-generic"} <= frameworks
    assert frameworks & {"java-generic", "java-spring"}
    # Verify no duplicate identities among endpoints
    seen = set()
    for ep in project.endpoints:
        identity = (ep.source_path, ep.line, ep.method, ep.path)
        assert identity not in seen, f"Duplicate endpoint: {identity}"
        seen.add(identity)
