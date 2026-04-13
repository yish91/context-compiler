from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceFile:
    absolute_path: Path
    relative_path: str
    language: str
    size_bytes: int
    sha1: str
    source_bytes: bytes = field(repr=False, default=b"")


@dataclass(slots=True)
class FrameworkHints:
    python: list[str] = field(default_factory=list)
    javascript: list[str] = field(default_factory=list)
    go: list[str] = field(default_factory=list)
    java: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScanInput:
    root: Path
    files: list[SourceFile]
    framework_hints: FrameworkHints


@dataclass(slots=True)
class Symbol:
    name: str
    kind: str
    source_path: str
    line: int
    docstring: str | None = None


@dataclass(slots=True)
class ImportEdge:
    source_path: str
    target_path: str
    raw: str
    resolved: bool = False


@dataclass(slots=True)
class Endpoint:
    method: str
    path: str
    handler: str
    source_path: str
    line: int
    framework: str


@dataclass(slots=True)
class DataModel:
    name: str
    kind: str
    fields: list[str]
    source_path: str
    line: int
    framework: str = ""


@dataclass(slots=True)
class Component:
    name: str
    props: list[str]
    source_path: str
    line: int
    framework: str = ""


@dataclass(slots=True)
class Entrypoint:
    name: str
    kind: str
    source_path: str
    line: int
    framework: str


@dataclass(slots=True)
class ConfigRef:
    name: str
    kind: str
    source_path: str
    line: int


@dataclass(slots=True)
class DocSignal:
    text: str
    source_path: str
    line: int


@dataclass(slots=True)
class ExtractedProject:
    root: Path
    files: list[SourceFile]
    framework_hints: FrameworkHints
    symbols: list[Symbol] = field(default_factory=list)
    import_edges: list[ImportEdge] = field(default_factory=list)
    config_refs: list[ConfigRef] = field(default_factory=list)
    doc_signals: list[DocSignal] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    data_models: list[DataModel] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    entrypoints: list[Entrypoint] = field(default_factory=list)


@dataclass(slots=True)
class HotFile:
    path: str
    indegree: int
    outdegree: int


@dataclass(slots=True)
class CompiledArticle:
    name: str
    title: str
    kind: str
    markdown: str
    source_paths: list[str]
    related_paths: list[str]


@dataclass(slots=True)
class CompiledProject:
    root: Path
    compiler_version: str
    files: list[SourceFile]
    summary: str
    overview: str
    architecture: str
    routes: str
    schema: str
    components: str
    config: str
    hot_files_markdown: str
    index: str
    map_json: dict[str, Any]
    hot_files: list[HotFile]
    articles: list[CompiledArticle] = field(default_factory=list)
