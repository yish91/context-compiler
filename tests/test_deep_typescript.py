from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.scanner import scan_repository


def test_typescript_pack_replaces_baseline_route_and_adds_provenance() -> None:
    repo = (Path(__file__).parent / "fixtures" / "deep_ts_repo").resolve()
    project = extract_project(scan_repository(repo))
    routes = [item for item in project.endpoints if item.path == "/users"]
    assert len(routes) == 1
    assert routes[0].framework == "typescript-express"
    assert routes[0].handler == "getUsers"
    cards = [item for item in project.components if item.name == "UserCard"]
    assert len(cards) == 1
    assert cards[0].framework == "typescript-react"
    assert set(cards[0].props) >= {"user", "onSelect"}
    assert any(item.name == "bootstrap" and item.framework == "typescript-generic" for item in project.entrypoints)


def test_typescript_pack_detects_frameworks_from_nested_package_json_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    api_dir = repo / "packages" / "api"
    web_dir = repo / "packages" / "web"
    (api_dir / "src").mkdir(parents=True)
    (web_dir / "src").mkdir(parents=True)
    (api_dir / "package.json").write_text(
        '{"dependencies":{"express":"^4.0.0"}}',
        encoding="utf-8",
    )
    (web_dir / "package.json").write_text(
        '{"dependencies":{"react":"^18.0.0"}}',
        encoding="utf-8",
    )
    (api_dir / "src" / "routes.ts").write_text(
        "app.get('/users', getUsers)\n",
        encoding="utf-8",
    )
    (web_dir / "src" / "UserCard.tsx").write_text(
        "export function UserCard({ user, onSelect }) { return <button />; }\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))

    routes = [item for item in project.endpoints if item.path == "/users"]
    cards = [item for item in project.components if item.name == "UserCard"]
    assert len(routes) == 1
    assert routes[0].framework == "typescript-express"
    assert len(cards) == 1
    assert cards[0].framework == "typescript-react"
