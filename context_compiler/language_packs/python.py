from __future__ import annotations

import re
from dataclasses import replace

from ..extractors.frameworks import project_uses
from ..models import (
    DataModel,
    Endpoint,
    Entrypoint,
    ExtractedProject,
    ScanInput,
    SourceFile,
)
from ..tree_sitter_runtime import node_text, parse_source
from .shared import (
    endpoint_key,
    entrypoint_key,
    merge_records,
    model_key,
)

DJANGO_PATH_RE = re.compile(r"""path\(\s*['"]([^'"]+)['"]""")
DJANGO_URL_RE = re.compile(r"""url\(\s*r?['"]([^'"]+)['"]""")
FASTAPI_DECORATOR_RE = re.compile(r"""\.(get|post|put|delete|patch|options|head)\(\s*['"]([^'"]+)['"]""")
FLASK_ROUTE_RE = re.compile(r"""\.route\(\s*['"]([^'"]+)['"]""")
FLASK_METHODS_RE = re.compile(r"""methods\s*=\s*\[([^\]]+)\]""")
FLASK_METHOD_RE = re.compile(r"""['"]([A-Za-z]+)['"]""")

DJANGO_MODEL_BASES = frozenset({"Model", "models.Model"})
ENTRYPOINT_FILES = frozenset({"main.py", "manage.py", "app.py", "server.py", "wsgi.py", "asgi.py"})
BOOTSTRAP_NAMES = frozenset({"main", "bootstrap", "create_app", "make_app"})


def enrich_python(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    is_django = project_uses(scan_input, "python", "django")
    is_fastapi = project_uses(scan_input, "python", "fastapi")
    is_flask = project_uses(scan_input, "python", "flask")
    has_framework = is_django or is_fastapi or is_flask
    has_entrypoints = _has_python_entrypoints(scan_input)

    if not has_framework and not has_entrypoints:
        return project

    new_endpoints: list[Endpoint] = []
    new_models: list[DataModel] = []
    new_entrypoints: list[Entrypoint] = []

    for source_file in scan_input.files:
        if source_file.language != "python":
            continue
        try:
            if is_fastapi or is_flask:
                new_endpoints.extend(
                    _python_framework_endpoints(
                        source_file,
                        include_fastapi=is_fastapi,
                        include_flask=is_flask,
                    )
                )
            if is_django:
                new_endpoints.extend(_django_endpoints(source_file))
                new_models.extend(_django_models(source_file))
            if has_entrypoints:
                new_entrypoints.extend(_python_entrypoints(source_file))
        except Exception:
            continue

    result = project
    if new_endpoints:
        result = replace(
            result,
            endpoints=_merge_python_endpoints(result.endpoints, new_endpoints),
        )
    if new_models:
        result = replace(result, data_models=merge_records(result.data_models, new_models, key=model_key))
    if new_entrypoints:
        result = replace(result, entrypoints=merge_records(result.entrypoints, new_entrypoints, key=entrypoint_key))
    return result


def _has_python_entrypoints(scan_input: ScanInput) -> bool:
    import os

    return any(
        sf.language == "python" and os.path.basename(sf.relative_path) in ENTRYPOINT_FILES
        for sf in scan_input.files
    )


def _django_endpoints(source_file: SourceFile) -> list[Endpoint]:
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    text = source.decode("utf-8", errors="replace")
    if "urlpatterns" not in text:
        return []
    out: list[Endpoint] = []
    for i, line in enumerate(text.splitlines(), 1):
        match = DJANGO_PATH_RE.search(line) or DJANGO_URL_RE.search(line)
        if match:
            path = match.group(1)
            handler = _extract_django_handler(line)
            out.append(
                Endpoint(
                    method="ANY",
                    path=path,
                    handler=handler,
                    source_path=source_file.relative_path,
                    line=i,
                    framework="python-django",
                )
            )
    return out


def _extract_django_handler(line: str) -> str:
    m = re.search(r"""(?:views\.)?([A-Za-z_][A-Za-z0-9_]*)""", line.split(",")[1]) if "," in line else None
    return m.group(1) if m else ""


def _django_models(source_file: SourceFile) -> list[DataModel]:
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    text = source.decode("utf-8", errors="replace")
    if "models.Model" not in text and "Model" not in text:
        return []
    try:
        tree = parse_source("python", source)
    except LookupError:
        return []
    out: list[DataModel] = []

    def visit(node: object) -> None:
        if node.type == "class_definition":
            name = None
            bases: list[str] = []
            for child in node.children:
                if child.type == "identifier" and name is None:
                    name = node_text(source, child)
                elif child.type == "argument_list":
                    for arg in child.children:
                        if arg.type in ("identifier", "attribute"):
                            bases.append(node_text(source, arg))
            if name and any(base in DJANGO_MODEL_BASES for base in bases):
                fields = _class_fields(node, source)
                out.append(
                    DataModel(
                        name=name,
                        kind="class",
                        fields=fields,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                        framework="python-django",
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _class_fields(class_node: object, source: bytes) -> list[str]:
    fields: list[str] = []
    for child in class_node.children:
        if child.type != "block":
            continue
        for stmt in child.children:
            if stmt.type == "expression_statement" and stmt.child_count:
                inner = stmt.children[0]
                if inner.type == "assignment":
                    name_node = inner.children[0] if inner.children else None
                    if name_node is not None and name_node.type == "identifier":
                        fields.append(node_text(source, name_node))
    return fields


def _python_entrypoints(source_file: SourceFile) -> list[Entrypoint]:
    import os

    basename = os.path.basename(source_file.relative_path)
    if basename not in ENTRYPOINT_FILES:
        return []
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    try:
        tree = parse_source("python", source)
    except LookupError:
        return []
    out: list[Entrypoint] = []

    def visit(node: object) -> None:
        if node.type == "function_definition":
            for child in node.children:
                if child.type == "identifier":
                    name = node_text(source, child)
                    if name in BOOTSTRAP_NAMES:
                        out.append(
                            Entrypoint(
                                name=name,
                                kind="application",
                                source_path=source_file.relative_path,
                                line=node.start_point[0] + 1,
                                framework="python-generic",
                            )
                        )
                    break
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _python_framework_endpoints(
    source_file: SourceFile,
    *,
    include_fastapi: bool,
    include_flask: bool,
) -> list[Endpoint]:
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    try:
        tree = parse_source("python", source)
    except LookupError:
        return []
    out: list[Endpoint] = []

    def visit(node: object) -> None:
        if node.type == "decorated_definition":
            out.extend(
                _decorated_framework_endpoints(
                    node,
                    source_file,
                    source,
                    include_fastapi=include_fastapi,
                    include_flask=include_flask,
                )
            )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _decorated_framework_endpoints(
    node: object,
    source_file: SourceFile,
    source: bytes,
    *,
    include_fastapi: bool,
    include_flask: bool,
) -> list[Endpoint]:
    handler = ""
    line = node.start_point[0] + 1
    decorators: list[str] = []
    for child in node.children:
        if child.type == "function_definition":
            for sub in child.children:
                if sub.type == "identifier":
                    handler = node_text(source, sub)
                    line = child.start_point[0] + 1
                    break
        elif child.type == "decorator":
            decorators.append(node_text(source, child))
    if not handler:
        return []

    out: list[Endpoint] = []
    for decorator in decorators:
        if include_fastapi:
            match = FASTAPI_DECORATOR_RE.search(decorator)
            if match:
                out.append(
                    Endpoint(
                        method=match.group(1).upper(),
                        path=match.group(2),
                        handler=handler,
                        source_path=source_file.relative_path,
                        line=line,
                        framework="python-fastapi",
                    )
                )
        if include_flask:
            match = FLASK_ROUTE_RE.search(decorator)
            if match:
                path = match.group(1)
                methods = _flask_methods(decorator)
                for method in methods:
                    out.append(
                        Endpoint(
                            method=method,
                            path=path,
                            handler=handler,
                            source_path=source_file.relative_path,
                            line=line,
                            framework="python-flask",
                        )
                    )
    return out


def _flask_methods(decorator: str) -> list[str]:
    methods_match = FLASK_METHODS_RE.search(decorator)
    if methods_match is None:
        return ["GET"]
    methods = [match.group(1).upper() for match in FLASK_METHOD_RE.finditer(methods_match.group(1))]
    return methods or ["GET"]


def _merge_python_endpoints(existing: list[Endpoint], incoming: list[Endpoint]) -> list[Endpoint]:
    merged = merge_records(existing, incoming, key=endpoint_key)
    rich_flask_routes = {
        (item.source_path, item.line, item.path)
        for item in incoming
        if item.framework == "python-flask"
    }
    if not rich_flask_routes:
        return merged
    return [
        item
        for item in merged
        if not (
            item.framework == "flask"
            and item.method == "ROUTE"
            and (item.source_path, item.line, item.path) in rich_flask_routes
        )
    ]
