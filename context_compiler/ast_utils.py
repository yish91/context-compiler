from __future__ import annotations

from collections.abc import Iterator

from tree_sitter import Tree

from .models import SourceFile
from .tree_sitter_runtime import node_text, parse_source


def read_source_bytes(source_file: SourceFile) -> bytes:
    """Return a source file's cached bytes, falling back to a disk read."""
    return source_file.source_bytes or source_file.absolute_path.read_bytes()


def decode_source(source: bytes) -> str:
    """Decode source bytes to text using the project-wide lenient policy."""
    return source.decode("utf-8", errors="replace")


def read_source_text(source_file: SourceFile) -> str:
    """Return a source file's decoded text."""
    return decode_source(read_source_bytes(source_file))


def line_at_offset(text: str, offset: int) -> int:
    """Return the 1-based line number for a character offset into ``text``."""
    return text[:offset].count("\n") + 1


def safe_parse(language: str, source: bytes) -> Tree | None:
    """Parse ``source`` for ``language``, returning ``None`` for unknown languages."""
    try:
        return parse_source(language, source)
    except LookupError:
        return None


def walk_preorder(node: object) -> Iterator:
    """Yield ``node`` and all of its descendants in pre-order."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def first_identifier(node: object, source: bytes) -> str | None:
    """Return the text of the first ``identifier`` child of ``node``."""
    for child in node.children:
        if child.type == "identifier":
            return node_text(source, child)
    return None


def go_struct_fields(struct_node: object, source: bytes) -> list[str]:
    """Collect the field names declared in a Go ``struct_type`` node."""
    fields: list[str] = []
    for child in struct_node.children:
        if child.type != "field_declaration_list":
            continue
        for decl in child.children:
            if decl.type == "field_declaration":
                for sub in decl.children:
                    if sub.type == "field_identifier":
                        fields.append(node_text(source, sub))
    return fields


def react_component_props(func_node: object, source: bytes) -> list[str]:
    """Collect destructured prop names from a React component function node."""
    for child in func_node.children:
        if child.type != "formal_parameters":
            continue
        for param in child.children:
            if param.type != "required_parameter":
                continue
            for sub in walk_preorder(param):
                if sub.type == "object_pattern":
                    names: list[str] = []
                    for obj_child in sub.children:
                        if obj_child.type == "shorthand_property_identifier_pattern":
                            names.append(node_text(source, obj_child))
                    return names
    return []
