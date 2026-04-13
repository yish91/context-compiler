from pathlib import Path

from context_compiler.extractors import extract_structure
from context_compiler.scanner import scan_repository


def _repo() -> Path:
    return (Path(__file__).parent / "fixtures" / "multilang_repo").resolve()


def test_scanner_picks_up_rust_and_java_files() -> None:
    result = scan_repository(_repo())
    langs = {file.language for file in result.files}
    rel = {file.relative_path for file in result.files}
    assert "rust" in langs
    assert "java" in langs
    assert "rust_app/src/lib.rs" in rel
    assert "java_app/src/com/example/App.java" in rel


def test_generic_extractor_finds_rust_symbols() -> None:
    project = extract_structure(scan_repository(_repo()))
    rust_symbols = {
        symbol.name
        for symbol in project.symbols
        if symbol.source_path.endswith(".rs")
    }
    assert "User" in rust_symbols
    assert "Greeter" in rust_symbols
    assert "bootstrap" in rust_symbols
    assert "shutdown" in rust_symbols


def test_generic_extractor_finds_rust_use_imports() -> None:
    project = extract_structure(scan_repository(_repo()))
    rust_imports = [
        edge for edge in project.import_edges if edge.source_path.endswith(".rs")
    ]
    targets = {edge.target_path for edge in rust_imports}
    assert any("HashMap" in target or "collections" in target for target in targets)
    assert any("io" in target for target in targets)


def test_generic_extractor_finds_java_classes_and_methods() -> None:
    project = extract_structure(scan_repository(_repo()))
    java_symbols = {
        (symbol.kind, symbol.name)
        for symbol in project.symbols
        if symbol.source_path.endswith(".java")
    }
    assert ("class", "App") in java_symbols
    assert ("class", "Settings") in java_symbols
    assert ("function", "bootstrap") in java_symbols
    assert ("function", "users") in java_symbols
    assert ("function", "load") in java_symbols


def test_generic_extractor_finds_java_imports() -> None:
    project = extract_structure(scan_repository(_repo()))
    java_targets = {
        edge.target_path
        for edge in project.import_edges
        if edge.source_path.endswith(".java")
    }
    assert any("java/util/List" in target for target in java_targets)
    assert any("java/util/Map" in target for target in java_targets)


def test_generic_extractor_normalizes_internal_java_imports_to_path_like_targets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "App.java").write_text(
        "package com.example;\n"
        "\n"
        "import com.example.users.UserService;\n"
        "\n"
        "public class App {}\n",
        encoding="utf-8",
    )
    users_dir = source_dir / "users"
    users_dir.mkdir()
    (users_dir / "UserService.java").write_text(
        "package com.example.users;\n"
        "\n"
        "public class UserService {}\n",
        encoding="utf-8",
    )

    project = extract_structure(scan_repository(repo))

    java_targets = {
        edge.target_path
        for edge in project.import_edges
        if edge.source_path.endswith("App.java")
    }
    assert "com/example/users/UserService" in java_targets


def test_generic_extractors_support_bash_powershell_and_cmd() -> None:
    repo = (Path(__file__).parent / "fixtures" / "script_repo").resolve()
    project = extract_structure(scan_repository(repo))
    symbol_names = {symbol.name for symbol in project.symbols}
    config_names = {ref.name for ref in project.config_refs}
    import_targets = {edge.target_path for edge in project.import_edges}
    assert "deploy" in symbol_names
    assert "bootstrap" in symbol_names
    assert "APP_ENV" in config_names
    assert any(target.endswith("common.sh") for target in import_targets)
