from __future__ import annotations

from ..models import Component, ExtractedProject, ScanInput, SourceFile
from ..tree_sitter_runtime import node_text, parse_source


def extract_components(scan_input: ScanInput, project: ExtractedProject) -> list[Component]:
    out: list[Component] = []
    for source_file in scan_input.files:
        if source_file.language != "tsx":
            continue
        source = source_file.source_bytes or source_file.absolute_path.read_bytes()
        out.extend(_tsx_components(source_file, source))
    return out


def _tsx_components(source_file: SourceFile, source: bytes) -> list[Component]:
    tree = parse_source(source_file.language, source)
    out: list[Component] = []

    def visit(node) -> None:
        if node.type == "function_declaration":
            name = _first_identifier(node, source)
            if name is not None and name[0].isupper():
                props = _component_props(node, source)
                out.append(
                    Component(
                        name=name,
                        props=props,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _first_identifier(node, source: bytes) -> str | None:
    for child in node.children:
        if child.type == "identifier":
            return node_text(source, child)
    return None


def _component_props(func_node, source: bytes) -> list[str]:
    for child in func_node.children:
        if child.type != "formal_parameters":
            continue
        for param in child.children:
            if param.type != "required_parameter":
                continue
            for sub in param.walk_preorder() if hasattr(param, "walk_preorder") else _walk(param):
                if sub.type == "object_pattern":
                    names: list[str] = []
                    for obj_child in sub.children:
                        if obj_child.type == "shorthand_property_identifier_pattern":
                            names.append(node_text(source, obj_child))
                    return names
    return []


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))
