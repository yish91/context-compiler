from __future__ import annotations

import re
from typing import Any

from ..models import ConfigRef, ImportEdge, SourceFile, Symbol

LABEL_PATTERN = re.compile(r"^:(\w+)", re.MULTILINE)
CALL_PATTERN = re.compile(r"(?i)^\s*call\s+([^\s%]+)", re.MULTILINE)
SET_PATTERN = re.compile(r"(?i)^\s*set\s+([A-Z_][A-Z0-9_]*)=", re.MULTILINE)
ENV_PATTERN = re.compile(r"%([A-Z_][A-Z0-9_]*)%")


def extract_cmd_facts(source_file: SourceFile) -> dict[str, Any]:
    source = source_file.source_bytes or source_file.absolute_path.read_bytes()
    text = source.decode("utf-8", errors="replace")
    symbols: list[Symbol] = []
    imports: list[ImportEdge] = []
    config_refs: list[ConfigRef] = []

    _extract_labels(text, source_file, symbols)
    _extract_calls(text, source_file, imports)
    _extract_env_refs(text, source_file, config_refs)

    return {"symbols": symbols, "imports": imports, "config_refs": config_refs}


def _extract_labels(text: str, source_file: SourceFile, symbols: list[Symbol]) -> None:
    for match in LABEL_PATTERN.finditer(text):
        name = match.group(1)
        if name.lower() == "eof":
            continue
        line = text[: match.start()].count("\n") + 1
        symbols.append(
            Symbol(
                name=name,
                kind="label",
                source_path=source_file.relative_path,
                line=line,
            )
        )


def _extract_calls(text: str, source_file: SourceFile, imports: list[ImportEdge]) -> None:
    for match in CALL_PATTERN.finditer(text):
        target = match.group(1)
        if target.startswith(":"):
            continue
        imports.append(
            ImportEdge(
                source_path=source_file.relative_path,
                target_path=target,
                raw=match.group(0).strip(),
            )
        )


def _extract_env_refs(text: str, source_file: SourceFile, config_refs: list[ConfigRef]) -> None:
    seen: set[str] = set()
    for match in SET_PATTERN.finditer(text):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            line = text[: match.start()].count("\n") + 1
            config_refs.append(
                ConfigRef(name=name, kind="env", source_path=source_file.relative_path, line=line)
            )
    for match in ENV_PATTERN.finditer(text):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            line = text[: match.start()].count("\n") + 1
            config_refs.append(
                ConfigRef(name=name, kind="env", source_path=source_file.relative_path, line=line)
            )
