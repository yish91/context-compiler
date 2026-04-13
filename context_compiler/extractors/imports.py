from __future__ import annotations

from pathlib import PurePosixPath

from ..language_profiles import get_profile
from ..models import ImportEdge, SourceFile
from ..tree_sitter_runtime import node_text


def extract_imports(tree, source_file: SourceFile, source: bytes) -> list[ImportEdge]:
    profile = get_profile(source_file.language)
    if profile is None or not profile.import_types:
        return []
    out: list[ImportEdge] = []

    def visit(node) -> None:
        if node.type in profile.import_types:
            target = _find_import_target(node, source, profile.import_target_types)
            if target is not None:
                resolved = _resolve_relative(source_file.relative_path, target)
                out.append(
                    ImportEdge(
                        source_path=source_file.relative_path,
                        target_path=resolved or target,
                        raw=node_text(source, node),
                        resolved=bool(resolved),
                    )
                )
            return
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return out


def _find_import_target(node, source: bytes, target_types: frozenset[str]) -> str | None:
    for descendant in _dfs(node):
        if descendant is node:
            continue
        if descendant.type in target_types:
            raw = node_text(source, descendant)
            target = _strip_quotes(raw)
            return _normalize_import_target(target, descendant.type)
    return None


def _dfs(node):
    yield node
    for child in node.children:
        yield from _dfs(child)


def _strip_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] in "\"'`" and stripped[-1] == stripped[0]:
        return stripped[1:-1]
    return stripped


def _normalize_import_target(target: str, node_type: str) -> str:
    if node_type in {"scoped_identifier", "qualified_identifier"} and "." in target:
        return target.replace(".", "/")
    return target


def _resolve_relative(source_path: str, raw_target: str) -> str | None:
    if not raw_target.startswith("."):
        return None
    base = PurePosixPath(source_path).parent
    joined = (base / raw_target).as_posix()
    parts: list[str] = []
    for part in joined.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) if parts else None
