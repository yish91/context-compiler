from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.scanner import scan_repository


def test_python_pack_adds_django_route_and_entrypoint_without_duplicates() -> None:
    repo = (Path(__file__).parent / "fixtures" / "deep_python_repo").resolve()
    project = extract_project(scan_repository(repo))
    routes = [item for item in project.endpoints if item.path == "/users/"]
    assert len(routes) == 1
    assert routes[0].framework == "python-django"
    assert routes[0].handler == "users"
    users = [item for item in project.data_models if item.name == "User"]
    assert len(users) == 1
    assert users[0].framework == "python-django"
    assert any(item.source_path.endswith("manage.py") and item.framework == "python-generic" for item in project.entrypoints)


def test_python_pack_upgrades_fastapi_routes_to_phase1_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "\n"
        "app = FastAPI()\n"
        "\n"
        "@app.get('/users')\n"
        "def list_users():\n"
        "    return []\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))

    routes = [item for item in project.endpoints if item.path == "/users"]
    assert len(routes) == 1
    assert routes[0].method == "GET"
    assert routes[0].framework == "python-fastapi"
    assert routes[0].handler == "list_users"


def test_python_pack_expands_flask_route_methods_and_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "from flask import Flask\n"
        "\n"
        "app = Flask(__name__)\n"
        "\n"
        "@app.route('/users', methods=['GET', 'POST'])\n"
        "def users():\n"
        "    return ''\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))

    routes = sorted(
        [item for item in project.endpoints if item.path == "/users"],
        key=lambda item: item.method,
    )
    assert [item.method for item in routes] == ["GET", "POST"]
    assert {item.framework for item in routes} == {"python-flask"}
    assert {item.handler for item in routes} == {"users"}
