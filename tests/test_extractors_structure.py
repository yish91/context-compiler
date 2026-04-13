from pathlib import Path

from context_compiler.extractors import extract_structure
from context_compiler.scanner import scan_repository


def _repo() -> Path:
    return (Path(__file__).parent / "fixtures" / "polyglot_repo").resolve()


def test_extract_structure_finds_symbols_and_import_edges() -> None:
    scan_input = scan_repository(_repo())
    project = extract_structure(scan_input)
    symbol_names = {symbol.name for symbol in project.symbols}
    assert "bootstrap" in symbol_names
    assert any(edge.source_path.endswith("index.ts") for edge in project.import_edges)


def test_extract_structure_finds_python_class_and_config_refs() -> None:
    project = extract_structure(scan_repository(_repo()))
    symbol_names = {symbol.name for symbol in project.symbols}
    assert "User" in symbol_names
    config_names = {ref.name for ref in project.config_refs}
    assert "APP_NAME" in config_names


def test_extract_structure_collects_module_docstrings() -> None:
    project = extract_structure(scan_repository(_repo()))
    assert any(
        signal.source_path.endswith("main.py") and "bootstrap" in signal.text.lower()
        for signal in project.doc_signals
    )


def test_extracted_project_supports_entrypoints_provenance_java_hints_and_cached_source_bytes() -> None:
    from context_compiler.models import Component, DataModel, Entrypoint, ExtractedProject, FrameworkHints, SourceFile

    file = SourceFile(
        absolute_path=Path("src/main/java/com/example/App.java"),
        relative_path="src/main/java/com/example/App.java",
        language="java",
        size_bytes=12,
        sha1="deadbeef",
        source_bytes=b"class App {}",
    )
    project = ExtractedProject(
        root=Path("."),
        files=[file],
        framework_hints=FrameworkHints(java=["spring"]),
    )
    project.entrypoints.append(
        Entrypoint(
            name="main",
            kind="application",
            source_path=file.relative_path,
            line=7,
            framework="java-generic",
        )
    )
    project.data_models.append(
        DataModel(
            name="User",
            kind="class",
            fields=["id"],
            source_path=file.relative_path,
            line=10,
            framework="java-spring",
        )
    )
    project.components.append(
        Component(
            name="UserCard",
            props=["user"],
            source_path="src/components/UserCard.tsx",
            line=3,
            framework="typescript-react",
        )
    )
    assert project.framework_hints.java == ["spring"]
    assert project.files[0].source_bytes == b"class App {}"
    assert project.entrypoints[0].framework == "java-generic"
    assert project.data_models[0].framework == "java-spring"
    assert project.components[0].framework == "typescript-react"
