from __future__ import annotations

import re

from ..models import ConfigRef, SourceFile

PROCESS_ENV = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")
PY_OS_ENVIRON_GET = re.compile(r"os\.environ\.get\(\s*['\"]([A-Z_][A-Z0-9_]*)['\"]")
PY_OS_GETENV = re.compile(r"os\.getenv\(\s*['\"]([A-Z_][A-Z0-9_]*)['\"]")
PY_OS_ENVIRON_INDEX = re.compile(r"os\.environ\[\s*['\"]([A-Z_][A-Z0-9_]*)['\"]")
GO_OS_GETENV = re.compile(r"os\.Getenv\(\s*\"([A-Z_][A-Z0-9_]*)\"")
JAVA_SPRING_VALUE = re.compile(r"""@Value\(\s*["']\$\{([A-Za-z_][A-Za-z0-9_.]*)[^"'}]*\}["']\s*\)""")
JAVA_GET_PROPERTY = re.compile(r"""\.getProperty\(\s*["']([A-Za-z_][A-Za-z0-9_.]*)["']""")


def extract_config_refs(tree, source_file: SourceFile, source: bytes) -> list[ConfigRef]:
    text = source.decode("utf-8", errors="replace")
    found: dict[str, ConfigRef] = {}
    patterns: list[tuple[re.Pattern[str], str]] = []
    if source_file.language in {"typescript", "tsx", "javascript"}:
        patterns.append((PROCESS_ENV, "env"))
    if source_file.language == "python":
        patterns.extend(
            [
                (PY_OS_ENVIRON_GET, "env"),
                (PY_OS_GETENV, "env"),
                (PY_OS_ENVIRON_INDEX, "env"),
            ]
        )
    if source_file.language == "go":
        patterns.append((GO_OS_GETENV, "env"))
    if source_file.language == "java":
        patterns.extend(
            [
                (JAVA_SPRING_VALUE, "env"),
                (JAVA_GET_PROPERTY, "env"),
            ]
        )
    for pattern, kind in patterns:
        for match in pattern.finditer(text):
            name = match.group(1)
            if name in found:
                continue
            line = text[: match.start()].count("\n") + 1
            found[name] = ConfigRef(
                name=name,
                kind=kind,
                source_path=source_file.relative_path,
                line=line,
            )
    return list(found.values())
