from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.scanner import scan_repository


def _repo() -> Path:
    return (Path(__file__).parent / "fixtures" / "polyglot_repo").resolve()


def test_extract_project_finds_endpoints_models_and_components() -> None:
    project = extract_project(scan_repository(_repo()))
    assert any(endpoint.path == "/health" for endpoint in project.endpoints)
    assert any(model.name == "User" for model in project.data_models)
    assert any(component.name == "Button" for component in project.components)


def test_endpoint_inventory_covers_python_and_go_handlers() -> None:
    project = extract_project(scan_repository(_repo()))
    paths = {(endpoint.framework, endpoint.path) for endpoint in project.endpoints}
    assert ("python-fastapi", "/users") in paths
    assert ("net/http", "/users") in paths
