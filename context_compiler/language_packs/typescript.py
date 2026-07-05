from __future__ import annotations

import re
from dataclasses import replace

from ..ast_utils import (
    first_identifier,
    line_at_offset,
    react_component_props,
    read_source_bytes,
    read_source_text,
    safe_parse,
    walk_preorder,
)
from ..extractors.frameworks import project_uses
from ..models import (
    Component,
    Endpoint,
    Entrypoint,
    ExtractedProject,
    ScanInput,
    SourceFile,
)
from .shared import (
    component_key,
    endpoint_key,
    entrypoint_key,
    merge_records,
)

EXPRESS_ROUTE = re.compile(
    r"\.(get|post|put|delete|patch|options|head)\(\s*['\"](/[^'\"]*)['\"]"
    r"(?:\s*,\s*([A-Za-z_][A-Za-z0-9_]*))?",
)

BOOTSTRAP_NAMES = frozenset({"bootstrap", "main", "start", "init", "setup"})
ENTRYPOINT_FILES = frozenset({
    "index.ts", "index.tsx", "server.ts", "server.tsx",
    "app.ts", "app.tsx", "main.ts", "main.tsx",
})


def enrich_typescript(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    has_express = project_uses(scan_input, "typescript", "express")
    has_react = project_uses(scan_input, "tsx", "react")

    if not has_express and not has_react and not _has_ts_entrypoints(scan_input):
        return project

    new_endpoints: list[Endpoint] = []
    new_components: list[Component] = []
    new_entrypoints: list[Entrypoint] = []

    for source_file in scan_input.files:
        try:
            if source_file.language in ("typescript", "tsx", "javascript") and has_express:
                new_endpoints.extend(_ts_deep_endpoints(source_file))
            if source_file.language == "tsx" and has_react:
                new_components.extend(_tsx_deep_components(source_file))
            if source_file.language in ("typescript", "tsx"):
                new_entrypoints.extend(_ts_entrypoints(source_file))
        except Exception:
            continue

    result = project
    if new_endpoints:
        result = replace(result, endpoints=merge_records(result.endpoints, new_endpoints, key=endpoint_key))
    if new_components:
        result = replace(result, components=merge_records(result.components, new_components, key=component_key))
    if new_entrypoints:
        result = replace(result, entrypoints=merge_records(result.entrypoints, new_entrypoints, key=entrypoint_key))
    return result


def _has_ts_entrypoints(scan_input: ScanInput) -> bool:
    import os

    return any(
        sf.language in ("typescript", "tsx")
        and os.path.basename(sf.relative_path) in ENTRYPOINT_FILES
        for sf in scan_input.files
    )


def _ts_deep_endpoints(source_file: SourceFile) -> list[Endpoint]:
    text = read_source_text(source_file)
    out: list[Endpoint] = []
    for match in EXPRESS_ROUTE.finditer(text):
        method, path = match.group(1), match.group(2)
        handler = match.group(3) or ""
        line = line_at_offset(text, match.start())
        out.append(
            Endpoint(
                method=method.upper(),
                path=path,
                handler=handler,
                source_path=source_file.relative_path,
                line=line,
                framework="typescript-express",
            )
        )
    return out


def _tsx_deep_components(source_file: SourceFile) -> list[Component]:
    source = read_source_bytes(source_file)
    tree = safe_parse(source_file.language, source)
    if tree is None:
        return []
    out: list[Component] = []
    for node in walk_preorder(tree.root_node):
        if node.type == "function_declaration":
            name = first_identifier(node, source)
            if name and name[0].isupper():
                props = react_component_props(node, source)
                out.append(
                    Component(
                        name=name,
                        props=props,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                        framework="typescript-react",
                    )
                )
    return out


def _ts_entrypoints(source_file: SourceFile) -> list[Entrypoint]:
    import os

    basename = os.path.basename(source_file.relative_path)
    if basename not in ENTRYPOINT_FILES:
        return []
    source = read_source_bytes(source_file)
    tree = safe_parse(source_file.language, source)
    if tree is None:
        return []
    out: list[Entrypoint] = []
    for node in walk_preorder(tree.root_node):
        if node.type == "function_declaration":
            name = first_identifier(node, source)
            if name and name.lower() in BOOTSTRAP_NAMES:
                out.append(
                    Entrypoint(
                        name=name,
                        kind="application",
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                        framework="typescript-generic",
                    )
                )
    return out
