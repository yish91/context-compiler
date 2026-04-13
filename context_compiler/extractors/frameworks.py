from __future__ import annotations

from ..models import ExtractedProject, ScanInput


def project_uses(scan_input: ScanInput, language: str, name: str) -> bool:
    hints = scan_input.framework_hints
    if language == "python":
        return name in hints.python
    if language in {"javascript", "typescript", "tsx"}:
        return name in hints.javascript
    if language == "go":
        return name in hints.go
    if language == "java":
        return name in hints.java
    return False


def python_symbol_lookup(project: ExtractedProject) -> set[str]:
    return {symbol.name for symbol in project.symbols if symbol.kind == "class"}
