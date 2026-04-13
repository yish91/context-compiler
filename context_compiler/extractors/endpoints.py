from __future__ import annotations

import re

from ..models import Endpoint, ExtractedProject, ScanInput, SourceFile
from ..tree_sitter_runtime import node_text, parse_source

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}

GO_HANDLE_FUNC = re.compile(r"HandleFunc\(\s*\"(/[^\"]*)\"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)")
GO_GIN = re.compile(
    r"\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*\"(/[^\"]*)\"\s*,\s*([A-Za-z_.][A-Za-z0-9_.]*)"
)
FLASK_ROUTE = re.compile(r"route\(\s*['\"](/[^'\"]*)['\"]")
EXPRESS_ROUTE = re.compile(
    r"\.(get|post|put|delete|patch|options|head)\(\s*['\"](/[^'\"]*)['\"]"
)


def extract_endpoints(scan_input: ScanInput, project: ExtractedProject) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for source_file in scan_input.files:
        source = source_file.source_bytes or source_file.absolute_path.read_bytes()
        if source_file.language == "python":
            endpoints.extend(_python_endpoints(source_file, source))
        elif source_file.language == "go":
            endpoints.extend(_go_endpoints(source_file, source))
        elif source_file.language in {"typescript", "tsx", "javascript"}:
            endpoints.extend(_ts_endpoints(source_file, source))
    return endpoints


def _python_endpoints(source_file: SourceFile, source: bytes) -> list[Endpoint]:
    tree = parse_source(source_file.language, source)
    found: list[Endpoint] = []

    def visit(node) -> None:
        if node.type == "decorated_definition":
            endpoint = _python_decorated_endpoint(node, source_file, source)
            if endpoint is not None:
                found.append(endpoint)
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return found


def _python_decorated_endpoint(node, source_file: SourceFile, source: bytes) -> Endpoint | None:
    func_name: str | None = None
    func_line = node.start_point[0] + 1
    for child in node.children:
        if child.type == "function_definition":
            for sub in child.children:
                if sub.type == "identifier":
                    func_name = node_text(source, sub)
                    func_line = sub.start_point[0] + 1
                    break
    if func_name is None:
        return None
    for child in node.children:
        if child.type != "decorator":
            continue
        call = _find_call(child)
        if call is None:
            continue
        attr = call.children[0] if call.children else None
        if attr is None or attr.type != "attribute":
            continue
        method_node = attr.children[-1] if attr.children else None
        if method_node is None or method_node.type != "identifier":
            continue
        method = node_text(source, method_node).lower()
        framework: str
        path: str | None = None
        if method in HTTP_METHODS:
            path = _first_string_arg(call, source)
            framework = "fastapi"
        elif method == "route":
            path = _first_string_arg(call, source)
            framework = "flask"
        else:
            continue
        if path is None:
            continue
        return Endpoint(
            method=method.upper() if method != "route" else "ROUTE",
            path=path,
            handler=func_name,
            source_path=source_file.relative_path,
            line=func_line,
            framework=framework,
        )
    return None


def _find_call(node):
    for child in node.children:
        if child.type == "call":
            return child
    return None


def _first_string_arg(call_node, source: bytes) -> str | None:
    for child in call_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "string":
                    text = node_text(source, arg)
                    stripped = text.strip()
                    if stripped.startswith(("'", '"')) and stripped.endswith(("'", '"')):
                        return stripped[1:-1]
                    return stripped
    return None


def _go_endpoints(source_file: SourceFile, source: bytes) -> list[Endpoint]:
    text = source.decode("utf-8", errors="replace")
    out: list[Endpoint] = []
    for match in GO_HANDLE_FUNC.finditer(text):
        path, handler = match.group(1), match.group(2)
        line = text[: match.start()].count("\n") + 1
        out.append(
            Endpoint(
                method="ANY",
                path=path,
                handler=handler,
                source_path=source_file.relative_path,
                line=line,
                framework="net/http",
            )
        )
    for match in GO_GIN.finditer(text):
        method, path, handler = match.group(1), match.group(2), match.group(3)
        line = text[: match.start()].count("\n") + 1
        out.append(
            Endpoint(
                method=method,
                path=path,
                handler=handler,
                source_path=source_file.relative_path,
                line=line,
                framework="gin",
            )
        )
    return out


def _ts_endpoints(source_file: SourceFile, source: bytes) -> list[Endpoint]:
    text = source.decode("utf-8", errors="replace")
    out: list[Endpoint] = []
    for match in EXPRESS_ROUTE.finditer(text):
        method, path = match.group(1), match.group(2)
        line = text[: match.start()].count("\n") + 1
        out.append(
            Endpoint(
                method=method.upper(),
                path=path,
                handler="",
                source_path=source_file.relative_path,
                line=line,
                framework="express",
            )
        )
    return out
