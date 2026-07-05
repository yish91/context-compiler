from pathlib import Path

from context_compiler.extractors.frameworks import project_uses, python_symbol_lookup
from context_compiler.models import (
    ExtractedProject,
    FrameworkHints,
    ScanInput,
    Symbol,
)


def _scan_input(hints: FrameworkHints) -> ScanInput:
    return ScanInput(root=Path("."), files=[], framework_hints=hints)


def test_project_uses_per_language() -> None:
    hints = FrameworkHints(
        python=["fastapi"],
        javascript=["react"],
        go=["gin"],
        java=["spring"],
    )
    scan_input = _scan_input(hints)
    assert project_uses(scan_input, "python", "fastapi")
    assert not project_uses(scan_input, "python", "flask")
    assert project_uses(scan_input, "typescript", "react")
    assert project_uses(scan_input, "tsx", "react")
    assert project_uses(scan_input, "javascript", "react")
    assert project_uses(scan_input, "go", "gin")
    assert project_uses(scan_input, "java", "spring")


def test_project_uses_unsupported_language_is_false() -> None:
    scan_input = _scan_input(FrameworkHints(python=["fastapi"]))
    assert not project_uses(scan_input, "rust", "actix")


def test_python_symbol_lookup_returns_class_names_only() -> None:
    project = ExtractedProject(
        root=Path("."),
        files=[],
        framework_hints=FrameworkHints(),
        symbols=[
            Symbol(name="User", kind="class", source_path="a.py", line=1),
            Symbol(name="Order", kind="class", source_path="a.py", line=5),
            Symbol(name="run", kind="function", source_path="a.py", line=9),
        ],
    )
    assert python_symbol_lookup(project) == {"User", "Order"}
