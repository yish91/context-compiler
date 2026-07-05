from __future__ import annotations

import os
import re
from dataclasses import replace

from ..ast_utils import (
    go_struct_fields,
    read_source_bytes,
    read_source_text,
    safe_parse,
    walk_preorder,
)
from ..extractors.frameworks import project_uses
from ..models import (
    DataModel,
    Endpoint,
    Entrypoint,
    ExtractedProject,
    ScanInput,
    SourceFile,
)
from ..tree_sitter_runtime import node_text
from .shared import (
    endpoint_key,
    entrypoint_key,
    merge_records,
    model_key,
)

GIN_GROUP_RE = re.compile(r"""\.Group\(\s*['"]([^'"]+)['"]\s*\)""")
GIN_ROUTE_RE = re.compile(
    r"""\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*['"]([^'"]+)['"]"""
    r"""\s*,\s*([A-Za-z_][A-Za-z0-9_.]*)"""
)
HTTP_HANDLE_FUNC_RE = re.compile(
    r"""HandleFunc\(\s*['"]([^'"]+)['"]\s*,\s*([A-Za-z_][A-Za-z0-9_]*)"""
)


GO_ENTRYPOINT_NAMES = frozenset({"main", "bootstrap", "init", "setup"})
GO_ENTRYPOINT_FILES = frozenset({"main.go", "server.go", "app.go"})


def enrich_go(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    has_gin = project_uses(scan_input, "go", "gin")
    has_http = project_uses(scan_input, "go", "net/http")
    has_entrypoints = _has_go_entrypoints(scan_input)

    if not has_gin and not has_http and not has_entrypoints:
        return project

    new_endpoints: list[Endpoint] = []
    new_models: list[DataModel] = []
    new_entrypoints: list[Entrypoint] = []

    for source_file in scan_input.files:
        if source_file.language != "go":
            continue
        try:
            if has_gin:
                new_endpoints.extend(_gin_grouped_endpoints(source_file))
            new_models.extend(_go_deep_models(source_file))
            new_entrypoints.extend(_go_entrypoints(source_file))
        except Exception:
            continue

    result = project
    if new_endpoints:
        result = replace(result, endpoints=merge_records(result.endpoints, new_endpoints, key=endpoint_key))
    if new_models:
        result = replace(result, data_models=merge_records(result.data_models, new_models, key=model_key))
    if new_entrypoints:
        result = replace(result, entrypoints=merge_records(result.entrypoints, new_entrypoints, key=entrypoint_key))
    return result


def _has_go_entrypoints(scan_input: ScanInput) -> bool:
    return any(
        sf.language == "go" and os.path.basename(sf.relative_path) in GO_ENTRYPOINT_FILES
        for sf in scan_input.files
    )


def _gin_grouped_endpoints(source_file: SourceFile) -> list[Endpoint]:
    text = read_source_text(source_file)
    lines = text.splitlines()

    groups: dict[str, str] = {}
    for line in lines:
        gm = re.search(r"""(\w+)\s*:=\s*\w+\.Group\(\s*['"]([^'"]+)['"]\s*\)""", line)
        if gm:
            groups[gm.group(1)] = gm.group(2)

    out: list[Endpoint] = []
    for i, line in enumerate(lines, 1):
        rm = re.search(
            r"""(\w+)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*['"]([^'"]+)['"]"""
            r"""\s*,\s*([A-Za-z_][A-Za-z0-9_.]*)""",
            line,
        )
        if rm:
            var, method, path, handler = rm.group(1), rm.group(2), rm.group(3), rm.group(4)
            prefix = groups.get(var, "")
            full_path = prefix + path
            out.append(
                Endpoint(
                    method=method,
                    path=full_path,
                    handler=handler,
                    source_path=source_file.relative_path,
                    line=i,
                    framework="go-gin",
                )
            )
    return out


def _go_deep_models(source_file: SourceFile) -> list[DataModel]:
    source = read_source_bytes(source_file)
    tree = safe_parse("go", source)
    if tree is None:
        return []
    out: list[DataModel] = []
    for node in walk_preorder(tree.root_node):
        if node.type != "type_declaration":
            continue
        for child in node.children:
            if child.type == "type_spec":
                name = None
                is_struct = False
                fields: list[str] = []
                for sub in child.children:
                    if sub.type == "type_identifier":
                        name = node_text(source, sub)
                    elif sub.type == "struct_type":
                        is_struct = True
                        fields = go_struct_fields(sub, source)
                if name and is_struct:
                    out.append(
                        DataModel(
                            name=name,
                            kind="struct",
                            fields=fields,
                            source_path=source_file.relative_path,
                            line=child.start_point[0] + 1,
                            framework="go-generic",
                        )
                    )
    return out


def _go_entrypoints(source_file: SourceFile) -> list[Entrypoint]:
    if os.path.basename(source_file.relative_path) not in GO_ENTRYPOINT_FILES:
        return []
    source = read_source_bytes(source_file)
    tree = safe_parse("go", source)
    if tree is None:
        return []
    out: list[Entrypoint] = []
    for node in walk_preorder(tree.root_node):
        if node.type == "function_declaration":
            for child in node.children:
                if child.type == "identifier":
                    name = node_text(source, child)
                    if name in GO_ENTRYPOINT_NAMES:
                        out.append(
                            Entrypoint(
                                name=name,
                                kind="application",
                                source_path=source_file.relative_path,
                                line=node.start_point[0] + 1,
                                framework="go-generic",
                            )
                        )
                    break
    return out
