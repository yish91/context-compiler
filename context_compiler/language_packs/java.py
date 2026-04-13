from __future__ import annotations

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

SPRING_CONTROLLER_ANNOTATIONS = frozenset({
    "RestController", "Controller",
})
SPRING_MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
    "RequestMapping": "ANY",
}
SPRING_ENTITY_ANNOTATIONS = frozenset({"Entity", "Table", "Document"})


def enrich_java(scan_input: ScanInput, project: ExtractedProject) -> ExtractedProject:
    if not _has_java_files(scan_input):
        return project

    new_entrypoints = _java_main_entrypoints(scan_input)
    result = project
    if new_entrypoints:
        result = replace(result, entrypoints=merge_records(result.entrypoints, new_entrypoints, key=entrypoint_key))

    if project_uses(scan_input, "java", "spring"):
        spring_endpoints = _spring_endpoints(scan_input)
        spring_models = _spring_models(scan_input)
        spring_entrypoints = _spring_boot_entrypoints(scan_input)
        if spring_endpoints:
            result = replace(result, endpoints=merge_records(result.endpoints, spring_endpoints, key=endpoint_key))
        if spring_models:
            result = replace(result, data_models=merge_records(result.data_models, spring_models, key=model_key))
        if spring_entrypoints:
            result = replace(result, entrypoints=merge_records(result.entrypoints, spring_entrypoints, key=entrypoint_key))

    return result


def _has_java_files(scan_input: ScanInput) -> bool:
    return any(sf.language == "java" for sf in scan_input.files)


def _java_main_entrypoints(scan_input: ScanInput) -> list[Entrypoint]:
    out: list[Entrypoint] = []
    for sf in scan_input.files:
        if sf.language != "java":
            continue
        try:
            source = sf.source_bytes or sf.absolute_path.read_bytes()
            tree = parse_source("java", source)
            _find_main_methods(tree, sf, source, out)
        except Exception:
            continue
    return out


def _find_main_methods(tree: object, sf: SourceFile, source: bytes, out: list[Entrypoint]) -> None:
    def visit(node: object) -> None:
        if node.type == "method_declaration":
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = node_text(source, child)
                    break
            if name == "main":
                out.append(
                    Entrypoint(
                        name="main",
                        kind="application",
                        source_path=sf.relative_path,
                        line=node.start_point[0] + 1,
                        framework="java-generic",
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)


def _spring_endpoints(scan_input: ScanInput) -> list[Endpoint]:
    out: list[Endpoint] = []
    for sf in scan_input.files:
        if sf.language != "java":
            continue
        try:
            source = sf.source_bytes or sf.absolute_path.read_bytes()
            text = source.decode("utf-8", errors="replace")
            if not any(anno in text for anno in SPRING_CONTROLLER_ANNOTATIONS):
                continue
            tree = parse_source("java", source)
            _extract_spring_routes(tree, sf, source, text, out)
        except Exception:
            continue
    return out


def _extract_spring_routes(tree: object, sf: SourceFile, source: bytes, text: str, out: list[Endpoint]) -> None:
    def visit(node: object) -> None:
        if node.type == "class_declaration":
            class_prefix = _class_request_mapping_path(node, source)
            _visit_class_methods(node, sf, source, class_prefix, out)
            return
        for child in node.children:
            visit(child)

    visit(tree.root_node)


def _class_request_mapping_path(class_node: object, source: bytes) -> str:
    annotations = _get_annotations(class_node, source)
    for anno_name, anno_path in annotations:
        if anno_name == "RequestMapping" and anno_path:
            return anno_path
    return ""


def _visit_class_methods(class_node: object, sf: SourceFile, source: bytes, class_prefix: str, out: list[Endpoint]) -> None:
    for child in class_node.children:
        if child.type == "class_body":
            for member in child.children:
                if member.type == "method_declaration":
                    method_name = None
                    for sub in member.children:
                        if sub.type == "identifier":
                            method_name = node_text(source, sub)
                            break
                    annotations = _get_annotations(member, source)
                    for anno_name, anno_path in annotations:
                        http_method = SPRING_MAPPING_ANNOTATIONS.get(anno_name)
                        if http_method:
                            path = _join_mapping_paths(class_prefix, anno_path)
                            out.append(
                                Endpoint(
                                    method=http_method,
                                    path=path,
                                    handler=method_name or "",
                                    source_path=sf.relative_path,
                                    line=member.start_point[0] + 1,
                                    framework="java-spring",
                                )
                            )
                            break


def _join_mapping_paths(class_prefix: str, method_path: str) -> str:
    if not class_prefix:
        return method_path
    if not method_path:
        return class_prefix
    left = class_prefix.rstrip("/")
    right = method_path if method_path.startswith("/") else f"/{method_path}"
    return f"{left}{right}"


def _get_annotations(node: object, source: bytes) -> list[tuple[str, str]]:
    annotations: list[tuple[str, str]] = []
    parent = node
    if hasattr(parent, "prev_named_sibling") and parent.prev_named_sibling:
        sib = parent.prev_named_sibling
        if sib.type == "modifiers":
            for child in sib.children:
                if child.type == "marker_annotation":
                    name = _annotation_name(child, source)
                    if name:
                        annotations.append((name, ""))
                elif child.type == "annotation":
                    name = _annotation_name(child, source)
                    path = _annotation_string_arg(child, source)
                    if name:
                        annotations.append((name, path))
    for child in node.children:
        if child.type == "modifiers":
            for sub in child.children:
                if sub.type == "marker_annotation":
                    name = _annotation_name(sub, source)
                    if name:
                        annotations.append((name, ""))
                elif sub.type == "annotation":
                    name = _annotation_name(sub, source)
                    path = _annotation_string_arg(sub, source)
                    if name:
                        annotations.append((name, path))
    return annotations


def _annotation_name(node: object, source: bytes) -> str | None:
    for child in node.children:
        if child.type == "identifier":
            return node_text(source, child)
    return None


def _annotation_string_arg(node: object, source: bytes) -> str:
    for child in node.children:
        if child.type == "annotation_argument_list":
            for arg in child.children:
                if arg.type == "string_literal":
                    text = node_text(source, arg)
                    return text.strip('"').strip("'")
                if arg.type == "element_value_pair":
                    for sub in arg.children:
                        if sub.type == "string_literal":
                            return node_text(source, sub).strip('"').strip("'")
    return ""


def _spring_models(scan_input: ScanInput) -> list[DataModel]:
    out: list[DataModel] = []
    for sf in scan_input.files:
        if sf.language != "java":
            continue
        try:
            source = sf.source_bytes or sf.absolute_path.read_bytes()
            text = source.decode("utf-8", errors="replace")
            if not any(anno in text for anno in SPRING_ENTITY_ANNOTATIONS):
                continue
            tree = parse_source("java", source)
            _extract_spring_models(tree, sf, source, out)
        except Exception:
            continue
    return out


def _extract_spring_models(tree: object, sf: SourceFile, source: bytes, out: list[DataModel]) -> None:
    def visit(node: object) -> None:
        if node.type == "class_declaration":
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = node_text(source, child)
                    break
            annotations = _get_annotations(node, source)
            if any(anno_name in SPRING_ENTITY_ANNOTATIONS for anno_name, _ in annotations):
                fields = _java_class_fields(node, source)
                out.append(
                    DataModel(
                        name=name or "",
                        kind="class",
                        fields=fields,
                        source_path=sf.relative_path,
                        line=node.start_point[0] + 1,
                        framework="java-spring",
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)


def _java_class_fields(class_node: object, source: bytes) -> list[str]:
    fields: list[str] = []
    for child in class_node.children:
        if child.type != "class_body":
            continue
        for member in child.children:
            if member.type == "field_declaration":
                for sub in member.children:
                    if sub.type == "variable_declarator":
                        for decl_child in sub.children:
                            if decl_child.type == "identifier":
                                fields.append(node_text(source, decl_child))
                                break
    return fields


def _spring_boot_entrypoints(scan_input: ScanInput) -> list[Entrypoint]:
    out: list[Entrypoint] = []
    for sf in scan_input.files:
        if sf.language != "java":
            continue
        try:
            source = sf.source_bytes or sf.absolute_path.read_bytes()
            text = source.decode("utf-8", errors="replace")
            if "@SpringBootApplication" not in text:
                continue
            tree = parse_source("java", source)
            _find_spring_boot_main(tree, sf, source, out)
        except Exception:
            continue
    return out


def _find_spring_boot_main(tree: object, sf: SourceFile, source: bytes, out: list[Entrypoint]) -> None:
    def visit(node: object) -> None:
        if node.type == "method_declaration":
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = node_text(source, child)
                    break
            if name == "main":
                out.append(
                    Entrypoint(
                        name="main",
                        kind="application",
                        source_path=sf.relative_path,
                        line=node.start_point[0] + 1,
                        framework="java-spring",
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
