from pathlib import Path

from context_compiler.extractors.endpoints import extract_endpoints
from context_compiler.models import ExtractedProject, FrameworkHints, ScanInput, SourceFile


def _project(source: str, language: str = "python", relative_path: str = "app.py") -> tuple[ScanInput, ExtractedProject]:
    source_bytes = source.encode("utf-8")
    source_file = SourceFile(
        absolute_path=Path(relative_path),
        relative_path=relative_path,
        language=language,
        size_bytes=len(source_bytes),
        sha1="x",
        source_bytes=source_bytes,
    )
    scan_input = ScanInput(root=Path("."), files=[source_file], framework_hints=FrameworkHints())
    project = ExtractedProject(root=Path("."), files=[source_file], framework_hints=FrameworkHints())
    return scan_input, project


def _endpoints(source: str, **kwargs):
    scan_input, project = _project(source, **kwargs)
    return extract_endpoints(scan_input, project)


def test_python_fastapi_and_flask_endpoints_detected() -> None:
    source = (
        "@app.get('/items')\n"
        "def list_items():\n"
        "    return []\n"
        "\n"
        "@app.route('/legacy')\n"
        "def legacy():\n"
        "    return ''\n"
    )
    endpoints = {(e.method, e.path, e.framework) for e in _endpoints(source)}
    assert ("GET", "/items", "fastapi") in endpoints
    assert ("ROUTE", "/legacy", "flask") in endpoints


def test_python_decorated_class_is_ignored() -> None:
    source = "@app.get('/thing')\nclass Thing:\n    pass\n"
    assert _endpoints(source) == []


def test_python_decorator_without_call_is_ignored() -> None:
    source = "@property\ndef value(self):\n    return 1\n"
    assert _endpoints(source) == []


def test_python_plain_identifier_decorator_is_ignored() -> None:
    source = "@lru_cache(maxsize=1)\ndef cached():\n    return 1\n"
    assert _endpoints(source) == []


def test_python_non_http_attribute_decorator_is_ignored() -> None:
    source = "@app.middleware('http')\nasync def mw(request, call_next):\n    return None\n"
    assert _endpoints(source) == []


def test_python_route_decorator_without_path_is_ignored() -> None:
    source = "@app.get()\ndef missing_path():\n    return None\n"
    assert _endpoints(source) == []


def test_python_route_with_keyword_only_args_is_ignored() -> None:
    source = "@app.get(status_code=200)\ndef no_path():\n    return None\n"
    assert _endpoints(source) == []


def test_python_raw_string_path_is_preserved_verbatim() -> None:
    source = "@app.get(r'/raw')\ndef raw():\n    return None\n"
    endpoints = _endpoints(source)
    assert len(endpoints) == 1
    assert endpoints[0].path == "r'/raw'"


def test_go_endpoints_net_http_and_gin() -> None:
    source = (
        "package main\n"
        'func setup(r *gin.Engine) {\n'
        '    http.HandleFunc("/health", healthHandler)\n'
        '    r.GET("/users", listUsers)\n'
        "}\n"
    )
    endpoints = {(e.method, e.path, e.framework) for e in _endpoints(source, language="go", relative_path="main.go")}
    assert ("ANY", "/health", "net/http") in endpoints
    assert ("GET", "/users", "gin") in endpoints


def test_typescript_express_endpoints() -> None:
    source = "router.get('/ping', handler);\nrouter.post('/submit', handler);\n"
    endpoints = {(e.method, e.path, e.framework) for e in _endpoints(source, language="typescript", relative_path="routes.ts")}
    assert ("GET", "/ping", "express") in endpoints
    assert ("POST", "/submit", "express") in endpoints
