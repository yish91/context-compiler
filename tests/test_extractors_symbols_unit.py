from pathlib import Path

from context_compiler.extractors.symbols import (
    _clean_string,
    extract_doc_signals,
    extract_symbols,
)
from context_compiler.models import SourceFile
from context_compiler.tree_sitter_runtime import parse_source


def _file(language: str, source: bytes, relative_path: str = "sample") -> SourceFile:
    return SourceFile(
        absolute_path=Path(relative_path),
        relative_path=relative_path,
        language=language,
        size_bytes=len(source),
        sha1="x",
        source_bytes=source,
    )


def test_extract_symbols_returns_empty_for_unsupported_language() -> None:
    source = b'{"a": 1}\n'
    tree = parse_source("python", source)
    source_file = _file("jsonnet", source, "config.jsonnet")
    assert extract_symbols(tree, source_file, source) == []


def test_extract_symbols_uses_name_node_fallback_for_kotlin_object() -> None:
    source = b"object AppConfig {\n    fun run() {}\n}\n"
    tree = parse_source("kotlin", source)
    source_file = _file("kotlin", source, "App.kt")
    symbols = extract_symbols(tree, source_file, source)
    classes = {symbol.name for symbol in symbols if symbol.kind == "class"}
    assert "AppConfig" in classes


def test_extract_doc_signals_reads_module_docstring() -> None:
    source = b'"""Top level module docstring."""\n\nx = 1\n'
    tree = parse_source("python", source)
    source_file = _file("python", source, "module.py")
    signals = extract_doc_signals(tree, source_file, source)
    assert len(signals) == 1
    assert signals[0].text == "Top level module docstring."
    assert signals[0].line == 1


def test_extract_doc_signals_empty_for_non_python() -> None:
    source = b"package main\n"
    tree = parse_source("go", source)
    source_file = _file("go", source, "main.go")
    assert extract_doc_signals(tree, source_file, source) == []


def test_clean_string_returns_raw_when_no_matching_quotes() -> None:
    assert _clean_string("no quotes here") == "no quotes here"


def test_clean_string_strips_triple_quotes() -> None:
    assert _clean_string('"""hello"""') == "hello"
