from __future__ import annotations

import re
from typing import Any

from ..ast_utils import decode_source, read_source_bytes, safe_parse, walk_preorder
from ..models import ConfigRef, ImportEdge, SourceFile, Symbol
from ..tree_sitter_runtime import node_text

SOURCE_PATTERN = re.compile(r"""(?:source|\.)\s+["']?([^\s"']+)["']?""")
ENV_PATTERN = re.compile(r"""\$\{?([A-Z_][A-Z0-9_]*)\}?""")


def extract_bash_facts(source_file: SourceFile) -> dict[str, Any]:
    source = read_source_bytes(source_file)
    symbols: list[Symbol] = []
    imports: list[ImportEdge] = []
    config_refs: list[ConfigRef] = []

    tree = safe_parse("bash", source)
    if tree is not None:
        _extract_tree_symbols(tree, source_file, source, symbols)

    text = decode_source(source)
    _extract_source_imports(text, source_file, imports)
    _extract_env_refs(text, source_file, config_refs)

    return {"symbols": symbols, "imports": imports, "config_refs": config_refs}


def _extract_tree_symbols(tree: Any, source_file: SourceFile, source: bytes, symbols: list[Symbol]) -> None:
    for node in walk_preorder(tree.root_node):
        if node.type != "function_definition":
            continue
        for child in node.children:
            if child.type in ("word", "variable_name"):
                symbols.append(
                    Symbol(
                        name=node_text(source, child),
                        kind="function",
                        source_path=source_file.relative_path,
                        line=node.start_point[0] + 1,
                    )
                )
                break


def _extract_source_imports(text: str, source_file: SourceFile, imports: list[ImportEdge]) -> None:
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        match = SOURCE_PATTERN.match(stripped)
        if match:
            target = match.group(1)
            imports.append(
                ImportEdge(
                    source_path=source_file.relative_path,
                    target_path=target,
                    raw=stripped,
                )
            )


def _extract_env_refs(text: str, source_file: SourceFile, config_refs: list[ConfigRef]) -> None:
    seen: set[str] = set()
    for i, line in enumerate(text.splitlines(), 1):
        for match in ENV_PATTERN.finditer(line):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                config_refs.append(
                    ConfigRef(
                        name=name,
                        kind="env",
                        source_path=source_file.relative_path,
                        line=i,
                    )
                )
