from __future__ import annotations

import time
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any

from . import __version__
from .budgets import compute_budget_profile, load_budget_settings
from .fs_utils import estimate_tokens
from .models import (
    CompiledProject,
    ExtractedProject,
    HotFile,
    ImportEdge,
    SourceFile,
)

# Relevance ranking for article selection (used by article builders)
from .relevance import get_file_scores as get_file_scores  # noqa: F401
from .relevance import rank_paths as rank_paths_by_relevance  # noqa: F401

# Article builders for generating compiled articles
from .article_builder import build_articles

COMPILER_VERSION = __version__

RESOLVABLE_SUFFIXES: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".go",
    ".java",
)

JAVA_SOURCE_ROOTS: tuple[str, ...] = (
    "src/main/java/",
    "src/test/java/",
)

# Legacy BUDGETS dict maintained for map.json artifact list and backwards compatibility
BUDGETS: dict[str, int] = {
    "index.md": 300,
    "overview.md": 600,
    "architecture.md": 900,
    "routes.md": 1200,
    "schema.md": 900,
    "components.md": 800,
    "config.md": 500,
    "hot-files.md": 300,
}


def compile_project(project: ExtractedProject) -> CompiledProject:
    resolved_edges = _resolve_edges(project)
    hot_files = _rank_hot_files(project.files, resolved_edges)

    # Compute adaptive budget profile based on project fact density
    settings = load_budget_settings(project.root)
    budget_profile = compute_budget_profile(project, resolved_edges, settings)

    # Build global artifacts with computed budgets
    overview = _fit_budget(budget_profile.overview, _build_overview(project))
    architecture = _fit_budget(
        budget_profile.architecture, _build_architecture(project, resolved_edges, hot_files)
    )
    routes = _fit_budget(budget_profile.routes, _build_routes(project))
    schema = _fit_budget(budget_profile.schema, _build_schema(project))
    components = _fit_budget(budget_profile.components, _build_components(project))
    config = _fit_budget(budget_profile.config, _build_config(project))
    hot_files_markdown = _fit_budget(budget_profile.hot_files, _build_hot_files_markdown(hot_files))

    # Build targeted articles with budget profile
    articles = build_articles(project, resolved_edges=resolved_edges, budget_profile=budget_profile)

    # Index is always fixed at 300
    index = _fit_budget(budget_profile.index, _build_index(project, articles))

    map_json = _build_map_json(project, resolved_edges, hot_files, articles)
    return CompiledProject(
        root=project.root,
        compiler_version=COMPILER_VERSION,
        files=list(project.files),
        summary="",
        overview=overview,
        architecture=architecture,
        routes=routes,
        schema=schema,
        components=components,
        config=config,
        hot_files_markdown=hot_files_markdown,
        index=index,
        map_json=map_json,
        hot_files=hot_files,
        articles=articles,
    )


def _resolve_edges(project: ExtractedProject) -> list[ImportEdge]:
    known: set[str] = {file.relative_path for file in project.files}
    out: list[ImportEdge] = []
    for edge in project.import_edges:
        target = edge.target_path
        resolved = _resolve_path(target, known)
        out.append(
            ImportEdge(
                source_path=edge.source_path,
                target_path=resolved or target,
                raw=edge.raw,
                resolved=bool(resolved),
            )
        )
    return out


def _resolve_path(target: str, known: set[str]) -> str | None:
    if target in known:
        return target
    java_resolved = _resolve_java_path(target, known)
    if java_resolved:
        return java_resolved
    for suffix in RESOLVABLE_SUFFIXES:
        candidate = target + suffix
        if candidate in known:
            return candidate
    for suffix in RESOLVABLE_SUFFIXES:
        candidate = target + "/index" + suffix
        if candidate in known:
            return candidate
    return None


def _resolve_java_path(target: str, known: set[str]) -> str | None:
    if "/" not in target:
        return None
    for root in JAVA_SOURCE_ROOTS:
        candidate = root + target + ".java"
        if candidate in known:
            return candidate
    return None


def _rank_hot_files(files: list[SourceFile], edges: list[ImportEdge]) -> list[HotFile]:
    indegree: Counter[str] = Counter()
    outdegree: Counter[str] = Counter()
    for edge in edges:
        if not edge.resolved:
            continue
        indegree[edge.target_path] += 1
        outdegree[edge.source_path] += 1
    ranked: list[HotFile] = []
    for file in files:
        ranked.append(
            HotFile(
                path=file.relative_path,
                indegree=indegree.get(file.relative_path, 0),
                outdegree=outdegree.get(file.relative_path, 0),
            )
        )
    ranked.sort(key=lambda hot: (-hot.indegree, -hot.outdegree, hot.path))
    return ranked


def _fit_budget(limit: int, text: str) -> str:
    """Fit text within a token budget, truncating if necessary.

    Args:
        limit: Maximum token budget.
        text: Text to fit within the budget.

    Returns:
        The text, truncated if necessary to fit within the budget.
    """
    if estimate_tokens(text) <= limit:
        return text
    max_chars = limit * 4
    lines = text.splitlines()
    kept: list[str] = []
    running = ""
    for line in lines:
        tentative = running + line + "\n"
        if estimate_tokens(tentative) > limit - 4:
            kept.append("...truncated to fit budget...")
            break
        running = tentative
        kept.append(line)
    result = "\n".join(kept).rstrip() + "\n"
    if estimate_tokens(result) > limit:
        result = result[: max_chars - 32].rstrip() + "\n...truncated...\n"
    return result


def _build_index(project: ExtractedProject, articles: list) -> str:
    languages = sorted({file.language for file in project.files})
    lines = ["# Repository Context", ""]
    if languages:
        lines.append(f"Polyglot project: {', '.join(languages)}.")
        lines.append("")
    lines.extend(
        [
            "## Read next",
            "1. `.context/overview.md` for orientation",
            "2. `.context/architecture.md` for structure",
            "3. `.context/routes.md` for API surface",
            "4. `.context/schema.md` for models",
            "5. `.context/components.md` for UI",
            "6. `.context/config.md` for env/config",
            "7. `.context/hot-files.md` for central files",
            "",
        ]
    )

    # Separate structure and domain articles
    structure_articles = [a for a in articles if a.kind == "structure"]
    domain_articles = [a for a in articles if a.kind == "domain"]
    database_article = next((a for a in articles if a.kind == "database"), None)

    if structure_articles or domain_articles or database_article:
        lines.append("## Targeted Articles")
        lines.append("")

        # Structure pages first
        for article in structure_articles:
            lines.append(f"- `.context/{article.name}.md` - {article.title}")

        # Domain pages second
        for article in domain_articles:
            lines.append(f"- `.context/{article.name}.md` - {article.title}")

        # Database article
        if database_article:
            lines.append(f"- `.context/{database_article.name}.md` - {database_article.title}")

        lines.append("")

    # Add question-to-article routing hints
    if structure_articles or domain_articles or database_article:
        lines.append("## Question Routing")
        lines.append("")

        for article in structure_articles:
            prefix = article.name.replace("subsystem-", "")
            pretty_prefix = prefix.replace("_", " ")
            lines.append(f"- {pretty_prefix} subsystem questions -> `{article.name}.md`")

        for article in domain_articles:
            domain = article.name.replace("domain-", "")
            pretty_domain = domain.replace("_", " ")
            lines.append(f"- {pretty_domain} domain questions -> `{article.name}.md`")

        if database_article:
            lines.append(f"- data model/schema questions -> `{database_article.name}.md`")

        lines.append("")

    lines.append("Prefer these artifacts over broad repo scans.")

    return "\n".join(lines) + "\n"


def _build_overview(project: ExtractedProject) -> str:
    lang_counts: Counter[str] = Counter(file.language for file in project.files)
    top_dirs: Counter[str] = Counter()
    for file in project.files:
        head = PurePosixPath(file.relative_path).parts[0] if "/" in file.relative_path else "."
        top_dirs[head] += 1
    lines = [
        "# Overview",
        "",
        f"Files parsed: {len(project.files)}",
        "",
        "## Languages",
    ]
    for lang, count in lang_counts.most_common():
        lines.append(f"- {lang}: {count}")
    lines.extend(["", "## Top-level directories"])
    for directory, count in top_dirs.most_common(10):
        lines.append(f"- `{directory}/`: {count} files")
    hints = project.framework_hints
    if hints.python or hints.javascript or hints.go or hints.java:
        lines.extend(["", "## Framework hints"])
        if hints.python:
            lines.append(f"- python: {', '.join(hints.python)}")
        if hints.javascript:
            lines.append(f"- javascript: {', '.join(hints.javascript)}")
        if hints.go:
            lines.append(f"- go: {', '.join(hints.go)}")
        if hints.java:
            lines.append(f"- java: {', '.join(hints.java)}")
    doc_hits = [signal for signal in project.doc_signals if signal.text]
    if doc_hits:
        lines.extend(["", "## Doc signals"])
        for signal in doc_hits[:5]:
            snippet = signal.text.strip().splitlines()[0][:120]
            lines.append(f"- `{signal.source_path}`: {snippet}")
    return "\n".join(lines) + "\n"


def _build_architecture(
    project: ExtractedProject,
    edges: list[ImportEdge],
    hot_files: list[HotFile],
) -> str:
    lines = ["# Architecture", ""]
    entry_points = _entry_points(project)
    if entry_points:
        lines.append("## Entry points")
        for entry in entry_points:
            suffix = f" [{entry['framework']}]" if entry.get("framework") else ""
            lines.append(f"- `{entry['path']}` — {entry['label']}{suffix}")
        lines.append("")
    resolved = [edge for edge in edges if edge.resolved]
    if resolved:
        lines.append("## Module dependency edges")
        grouped: dict[str, list[str]] = defaultdict(list)
        for edge in resolved:
            grouped[edge.source_path].append(edge.target_path)
        for source in sorted(grouped)[:20]:
            targets = ", ".join(sorted(set(grouped[source]))[:6])
            lines.append(f"- `{source}` → {targets}")
        lines.append("")
    if hot_files:
        lines.append("## Central files")
        for hot in hot_files[:5]:
            if hot.indegree == 0 and hot.outdegree == 0:
                break
            lines.append(f"- `{hot.path}` (in={hot.indegree}, out={hot.outdegree})")
    return "\n".join(lines) + "\n"


def _entry_points(project: ExtractedProject) -> list[dict[str, str]]:
    if project.entrypoints:
        return [
            {
                "path": item.source_path,
                "label": item.name,
                "framework": item.framework,
                "kind": item.kind,
            }
            for item in sorted(
                project.entrypoints, key=lambda item: (item.source_path, item.line, item.name)
            )
        ]
    return _heuristic_entry_points(project)


def _heuristic_entry_points(project: ExtractedProject) -> list[dict[str, str]]:
    candidates: dict[str, list[str]] = {}
    priority = (
        "main.py",
        "main.go",
        "index.ts",
        "index.tsx",
        "index.js",
        "app.py",
        "server.ts",
        "app.ts",
        "main.ts",
    )
    for file in project.files:
        base = PurePosixPath(file.relative_path).name
        if base in priority:
            candidates[file.relative_path] = [
                symbol.name
                for symbol in project.symbols
                if symbol.source_path == file.relative_path
            ]
    return [
        {
            "path": path,
            "label": ", ".join(symbols[:6]) if symbols else path,
            "framework": "",
            "kind": "heuristic",
        }
        for path, symbols in sorted(candidates.items())
    ]


def _build_routes(project: ExtractedProject) -> str:
    lines = ["# Routes", ""]
    if not project.endpoints:
        lines.append("_No endpoints detected._")
        return "\n".join(lines) + "\n"
    by_framework: dict[str, list] = defaultdict(list)
    for endpoint in project.endpoints:
        by_framework[endpoint.framework].append(endpoint)
    for framework in sorted(by_framework):
        lines.append(f"## {framework}")
        for endpoint in sorted(by_framework[framework], key=lambda e: (e.path, e.method)):
            handler = f" — `{endpoint.handler}`" if endpoint.handler else ""
            lines.append(
                f"- `{endpoint.method} {endpoint.path}`{handler} "
                f"({endpoint.source_path}:{endpoint.line})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_schema(project: ExtractedProject) -> str:
    lines = ["# Schema", ""]
    if not project.data_models:
        lines.append("_No data models detected._")
        return "\n".join(lines) + "\n"
    for model in sorted(project.data_models, key=lambda m: (m.source_path, m.line)):
        fields = ", ".join(model.fields[:10]) if model.fields else ""
        suffix = f" — fields: {fields}" if fields else ""
        lines.append(
            f"- `{model.name}` ({model.kind}) in `{model.source_path}:{model.line}`{suffix}"
        )
    return "\n".join(lines) + "\n"


def _build_components(project: ExtractedProject) -> str:
    lines = ["# Components", ""]
    if not project.components:
        lines.append("_No UI components detected._")
        return "\n".join(lines) + "\n"
    for component in sorted(project.components, key=lambda c: (c.source_path, c.line)):
        props = ", ".join(component.props) if component.props else ""
        suffix = f" — props: {props}" if props else ""
        lines.append(f"- `{component.name}` in `{component.source_path}:{component.line}`{suffix}")
    return "\n".join(lines) + "\n"


def _build_config(project: ExtractedProject) -> str:
    lines = ["# Config", ""]
    if not project.config_refs:
        lines.append("_No config references detected._")
        return "\n".join(lines) + "\n"
    by_kind: dict[str, list] = defaultdict(list)
    for ref in sorted(project.config_refs, key=lambda r: (r.name, r.source_path)):
        by_kind[ref.kind].append(ref)
    for kind in sorted(by_kind):
        heading = "Environment variables" if kind == "env" else kind.replace("_", " ").title()
        lines.append(f"## {heading}")
        seen: set[str] = set()
        for ref in by_kind[kind]:
            if ref.name in seen:
                continue
            seen.add(ref.name)
            lines.append(f"- `{ref.name}` ({ref.source_path}:{ref.line})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_hot_files_markdown(hot_files: list[HotFile]) -> str:
    lines = [
        "# Hot Files",
        "",
        "Ranked by reverse-import indegree, then outdegree, then path.",
        "",
    ]
    meaningful = [hot for hot in hot_files if hot.indegree or hot.outdegree]
    if not meaningful:
        lines.append("_No import graph signal yet._")
        return "\n".join(lines) + "\n"
    for i, hot in enumerate(meaningful[:15], start=1):
        lines.append(f"{i}. `{hot.path}` (in={hot.indegree}, out={hot.outdegree})")
    return "\n".join(lines) + "\n"


def _build_map_json(
    project: ExtractedProject,
    edges: list[ImportEdge],
    hot_files: list[HotFile],
    articles: list | None = None,
) -> dict[str, Any]:
    return {
        "metadata": {
            "repo_root": str(project.root),
            "compiler_version": COMPILER_VERSION,
            "scan_time": int(time.time()),
        },
        "artifacts": list(BUDGETS.keys()),
        "files": [
            {
                "path": file.relative_path,
                "language": file.language,
                "size_bytes": file.size_bytes,
                "sha1": file.sha1,
            }
            for file in project.files
        ],
        "symbols": [
            {
                "name": s.name,
                "kind": s.kind,
                "path": s.source_path,
                "line": s.line,
            }
            for s in project.symbols
        ],
        "edges": [
            {
                "source": e.source_path,
                "target": e.target_path,
                "resolved": e.resolved,
            }
            for e in edges
        ],
        "endpoints": [
            {
                "method": e.method,
                "path": e.path,
                "handler": e.handler,
                "framework": e.framework,
                "source": e.source_path,
                "line": e.line,
            }
            for e in project.endpoints
        ],
        "models": [
            {
                "name": m.name,
                "kind": m.kind,
                "fields": m.fields,
                "source": m.source_path,
                "line": m.line,
            }
            for m in project.data_models
        ],
        "components": [
            {
                "name": c.name,
                "props": c.props,
                "source": c.source_path,
                "line": c.line,
            }
            for c in project.components
        ],
        "config_refs": [
            {
                "name": c.name,
                "kind": c.kind,
                "source": c.source_path,
                "line": c.line,
            }
            for c in project.config_refs
        ],
        "hot_files": [
            {"path": h.path, "indegree": h.indegree, "outdegree": h.outdegree} for h in hot_files
        ],
        "entrypoints": [
            {
                "name": e.name,
                "kind": e.kind,
                "source": e.source_path,
                "line": e.line,
                "framework": e.framework,
            }
            for e in project.entrypoints
        ],
        "articles": [
            {
                "name": a.name,
                "title": a.title,
                "kind": a.kind,
                "source_paths": a.source_paths,
                "related_paths": a.related_paths,
            }
            for a in (articles or [])
        ],
    }
