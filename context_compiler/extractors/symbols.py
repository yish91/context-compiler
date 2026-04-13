from __future__ import annotations

from ..language_profiles import get_profile
from ..models import DocSignal, SourceFile, Symbol
from ..tree_sitter_runtime import node_text

NAME_NODE_TYPES: frozenset[str] = frozenset(
    {"identifier", "type_identifier", "field_identifier", "property_identifier"}
)


def extract_symbols(tree, source_file: SourceFile, source: bytes) -> list[Symbol]:
    profile = get_profile(source_file.language)
    if profile is None:
        return []
    out: list[Symbol] = []

    def visit(node) -> None:
        if node.type in profile.function_types:
            name = _symbol_name(node, source)
            if name:
                out.append(
                    Symbol(
                        name=name,
                        kind="function",
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
        elif node.type in profile.class_types:
            name = _symbol_name(node, source)
            if name:
                out.append(
                    Symbol(
                        name=name,
                        kind="class",
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _symbol_name(node, source: bytes) -> str | None:
    field_node = node.child_by_field_name("name")
    if field_node is not None:
        return node_text(source, field_node)
    for child in node.children:
        if child.type in NAME_NODE_TYPES:
            return node_text(source, child)
    return None


def extract_doc_signals(tree, source_file: SourceFile, source: bytes) -> list[DocSignal]:
    if source_file.language != "python":
        return []
    signals: list[DocSignal] = []
    for child in tree.root_node.children:
        if child.type == "expression_statement" and child.child_count:
            first = child.children[0]
            if first.type == "string":
                signals.append(
                    DocSignal(
                        text=_clean_string(node_text(source, first)),
                        source_path=source_file.relative_path,
                        line=first.start_point[0] + 1,
                    )
                )
                break
        if child.type == "string":
            signals.append(
                DocSignal(
                    text=_clean_string(node_text(source, child)),
                    source_path=source_file.relative_path,
                    line=child.start_point[0] + 1,
                )
            )
            break
    return signals


def _clean_string(raw: str) -> str:
    stripped = raw.strip()
    for quote in ('"""', "'''", '"', "'"):
        if stripped.startswith(quote) and stripped.endswith(quote):
            return stripped[len(quote) : -len(quote)].strip()
    return stripped
