from __future__ import annotations

from ..ast_utils import (
    first_identifier,
    react_component_props,
    read_source_bytes,
    walk_preorder,
)
from ..models import Component, ExtractedProject, ScanInput, SourceFile
from ..tree_sitter_runtime import parse_source


def extract_components(scan_input: ScanInput, project: ExtractedProject) -> list[Component]:
    out: list[Component] = []
    for source_file in scan_input.files:
        if source_file.language != "tsx":
            continue
        source = read_source_bytes(source_file)
        out.extend(_tsx_components(source_file, source))
    return out


def _tsx_components(source_file: SourceFile, source: bytes) -> list[Component]:
    tree = parse_source(source_file.language, source)
    out: list[Component] = []
    for node in walk_preorder(tree.root_node):
        if node.type == "function_declaration":
            name = first_identifier(node, source)
            if name is not None and name[0].isupper():
                props = react_component_props(node, source)
                out.append(
                    Component(
                        name=name,
                        props=props,
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
    return out
