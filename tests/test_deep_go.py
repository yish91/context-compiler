from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.scanner import scan_repository


def test_go_pack_resolves_grouped_routes_without_duplicates() -> None:
    repo = (Path(__file__).parent / "fixtures" / "deep_go_repo").resolve()
    project = extract_project(scan_repository(repo))
    routes = [item for item in project.endpoints if item.path == "/api/v1/users" and item.method == "GET"]
    assert len(routes) == 1
    assert routes[0].framework == "go-gin"
    assert routes[0].handler == "listUsers"
    users = [item for item in project.data_models if item.name == "User"]
    assert len(users) == 1
    assert users[0].framework == "go-generic"
    assert any(item.source_path.endswith("cmd/api/main.go") and item.framework == "go-generic" for item in project.entrypoints)


def test_go_pack_detects_bootstrap_entrypoints_outside_main_go(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    service_dir = repo / "cmd" / "api"
    service_dir.mkdir(parents=True)
    (service_dir / "server.go").write_text(
        "package main\n"
        "\n"
        "func bootstrap() {}\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))

    assert any(
        item.source_path.endswith("cmd/api/server.go")
        and item.name == "bootstrap"
        and item.framework == "go-generic"
        for item in project.entrypoints
    )
