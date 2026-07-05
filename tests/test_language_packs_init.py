from pathlib import Path

import context_compiler.language_packs as language_packs
from context_compiler.language_packs import run_language_packs
from context_compiler.models import ExtractedProject, FrameworkHints, ScanInput


def _inputs() -> tuple[ScanInput, ExtractedProject]:
    scan_input = ScanInput(root=Path("."), files=[], framework_hints=FrameworkHints())
    project = ExtractedProject(root=Path("."), files=[], framework_hints=FrameworkHints())
    return scan_input, project


def test_run_language_packs_swallows_pack_exceptions(monkeypatch) -> None:
    def boom(scan_input, project):
        raise RuntimeError("pack exploded")

    import context_compiler.language_packs.python as python_pack

    monkeypatch.setattr(python_pack, "enrich_python", boom)

    scan_input, project = _inputs()
    result = run_language_packs(scan_input, project)
    # Failure in one pack must not abort the pipeline; the project is returned.
    assert result is not None
    assert isinstance(result, ExtractedProject)


def test_run_language_packs_returns_project_unchanged_when_no_files() -> None:
    scan_input, project = _inputs()
    result = run_language_packs(scan_input, project)
    assert result.symbols == []
    assert result.endpoints == []
    assert language_packs.logger.name == "context_compiler.language_packs"
