from __future__ import annotations

import re
from typing import Any

from ..models import ConfigRef, SourceFile, Symbol
from ..tree_sitter_runtime import node_text, parse_source

ENV_PATTERN = re.compile(r"""\$env:([A-Z_][A-Z0-9_]*)""", re.IGNORECASE)


def extract_powershell_facts(source_file: SourceFile) -> dict[str, Any]:
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    symbols: list[Symbol] = []
    config_refs: list[ConfigRef] = []

    try:
        tree = parse_source("powershell", source)
        _extract_tree_symbols(tree, source_file, source, symbols)
    except LookupError:
        pass

    text = source.decode("utf-8", errors="replace")
    _extract_env_refs(text, source_file, config_refs)

    return {"symbols": symbols, "imports": [], "config_refs": config_refs}


def _extract_tree_symbols(tree: Any, source_file: SourceFile, source: bytes, symbols: list[Symbol]) -> None:
    def visit(node: Any) -> None:
        if node.type == "function_statement":
            for child in node.children:
                if child.type == "function_name":
                    symbols.append(
                        Symbol(
                            name=node_text(source, child),
                            kind="function",
                            source_path=source_file.relative_path,
                            line=node.start_point[0] + 1,
                        )
                    )
                    break
        for child in node.children:
            visit(child)

    visit(tree.root_node)


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
