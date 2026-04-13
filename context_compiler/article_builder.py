"""Article builder for generating compiled articles from extracted projects.

This module generates structure articles for top-level subsystems like `api/`
and `web/`. It also generates domain articles for cross-cutting domains like
`auth` when multiple signal types agree on the domain.

It uses relevance scoring, fact density, and import cohesion to identify
strong subsystem boundaries and domain clusters.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .fs_utils import estimate_tokens, is_runtime_like_path
from .models import CompiledArticle, ExtractedProject, ImportEdge
from .relevance import get_file_scores

if TYPE_CHECKING:
    from .budgets import BudgetProfile

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Maximum total targeted articles (structure + domain)
MAX_TOTAL_ARTICLES: int = 8

# Maximum structure articles to emit
MAX_STRUCTURE_ARTICLES: int = 5

# Maximum domain articles to emit
MAX_DOMAIN_ARTICLES: int = 3

# Maximum candidates to score (large-repo guardrail)
MAX_CANDIDATES_TO_SCORE: int = 20

# Minimum files required to consider a directory as a subsystem
MIN_FILES_FOR_SUBSYSTEM: int = 2

# Minimum distinct fact types required for a domain article
MIN_DOMAIN_FACT_TYPES: int = 3

# Weak candidate prefixes to discard
WEAK_PREFIXES: frozenset[str] = frozenset(
    {
        "test",
        "tests",
        "spec",
        "specs",
        "fixture",
        "fixtures",
        "script",
        "scripts",
        "tool",
        "tools",
        "util",
        "utils",
        "utility",
        "utilities",
        "helper",
        "helpers",
        "doc",
        "docs",
        "documentation",
        "example",
        "examples",
        "sample",
        "samples",
        "demo",
        "demos",
        "config",
        "configs",
        "configuration",
        ".github",
        ".vscode",
        ".idea",
    }
)

# Minimum score threshold to emit an article
MIN_SCORE_THRESHOLD: int = 15

# Article token budget for structure/domain articles
ARTICLE_TOKEN_BUDGET: int = 700

# Database article has a larger budget per spec
DATABASE_TOKEN_BUDGET: int = 800

# Section priority for budget enforcement (higher = more important)
SECTION_PRIORITY: dict[str, int] = {
    "summary": 100,
    "key_files": 90,
    "routes": 80,
    "models": 70,
    "components": 60,
    "config": 50,
    "also_inspect": 40,
}


@dataclass(slots=True)
class SubsystemCandidate:
    """A candidate subsystem for article generation."""

    prefix: str
    file_count: int
    fact_count: int  # routes, models, components, config refs
    entrypoint_count: int
    relevance_sum: int
    import_cohesion: float  # 0-1, fraction of internal imports that resolve


# Domain fact type constants for multi-signal evidence
FACT_TYPE_ROUTE_PATH: str = "route_path"
FACT_TYPE_ROUTE_FILENAME: str = "route_filename"
FACT_TYPE_MODEL_NAME: str = "model_name"
FACT_TYPE_CONFIG_NAME: str = "config_name"
FACT_TYPE_HOT_FILENAME: str = "hot_filename"
FACT_TYPE_IMPORT_FILENAME: str = "import_filename"


@dataclass(slots=True)
class DomainCandidate:
    """A candidate domain for article generation."""

    name: str
    fact_types: set[str] = field(default_factory=set)
    route_paths: list[str] = field(default_factory=list)
    route_files: list[str] = field(default_factory=list)
    model_names: list[str] = field(default_factory=list)
    config_names: list[str] = field(default_factory=list)
    hot_files: list[str] = field(default_factory=list)
    import_files: list[str] = field(default_factory=list)

    @property
    def signal_count(self) -> int:
        """Total number of distinct fact types supporting this domain."""
        return len(self.fact_types)


def build_articles(
    project: ExtractedProject,
    resolved_edges: list[ImportEdge] | None = None,
    budget_profile: "BudgetProfile | None" = None,
) -> list[CompiledArticle]:
    """Build compiled articles from an extracted project.

    Generates both structure articles for subsystem boundaries and domain
    articles for cross-cutting domains with multi-signal evidence.
    Also generates a special database article if data models exist.

    Args:
        project: The extracted project to build articles from.
        resolved_edges: Fully resolved import edges (with file extensions).
            If None, falls back to project.import_edges.
        budget_profile: Computed budget profile for adaptive budgets.
            If None, uses fixed default budgets.

    Returns:
        A list of CompiledArticle objects (structure + domain + database articles).
    """
    # Use resolved edges if provided, otherwise fall back to project edges
    edges = resolved_edges if resolved_edges is not None else project.import_edges

    # Get budgets from profile or use defaults
    structure_budget = budget_profile.structure_article if budget_profile else ARTICLE_TOKEN_BUDGET
    domain_budget = budget_profile.domain_article if budget_profile else ARTICLE_TOKEN_BUDGET
    database_budget = budget_profile.database if budget_profile else DATABASE_TOKEN_BUDGET
    article_max = budget_profile.structure_article_max if budget_profile else ARTICLE_TOKEN_BUDGET

    articles: list[CompiledArticle] = []

    # Build structure articles
    structure_articles = _build_structure_articles(project, edges, structure_budget, article_max)
    articles.extend(structure_articles)

    # Build domain articles
    domain_articles = _build_domain_articles(project, edges, domain_budget)
    articles.extend(domain_articles)

    # Respect total cap for structure + domain
    if len(articles) > MAX_TOTAL_ARTICLES:
        articles = articles[:MAX_TOTAL_ARTICLES]

    # Build database article if models exist (special article, doesn't count toward cap)
    database_article = _build_database_article(project, edges, database_budget)
    if database_article:
        articles.append(database_article)

    return articles


def _build_structure_articles(
    project: ExtractedProject,
    edges: list[ImportEdge],
    base_budget: int = ARTICLE_TOKEN_BUDGET,
    max_budget: int = ARTICLE_TOKEN_BUDGET,
) -> list[CompiledArticle]:
    """Build structure articles for top-level subsystems.

    Args:
        project: The extracted project.
        edges: Fully resolved import edges.
        base_budget: Base token budget for structure articles.
        max_budget: Maximum token budget for structure articles.

    Returns:
        A list of structure articles.
    """
    candidates = _collect_subsystem_candidates(project, edges)

    # Cap candidates before expensive scoring
    if len(candidates) > MAX_CANDIDATES_TO_SCORE:
        # Sort by file count descending to keep most substantial directories
        candidates.sort(key=lambda c: -c.file_count)
        candidates = candidates[:MAX_CANDIDATES_TO_SCORE]

    # Score and rank candidates
    scored = [(c, _score_candidate(c)) for c in candidates]
    scored.sort(key=lambda x: -x[1])

    # Emit articles for strong candidates
    articles: list[CompiledArticle] = []
    for candidate, score in scored:
        if score < MIN_SCORE_THRESHOLD:
            continue
        if len(articles) >= MAX_STRUCTURE_ARTICLES:
            break
        articles.append(_build_structure_article(project, candidate, edges, base_budget, max_budget))

    return articles


def _collect_subsystem_candidates(
    project: ExtractedProject, edges: list[ImportEdge]
) -> list[SubsystemCandidate]:
    """Collect candidate subsystems from top-level directories."""
    file_scores = get_file_scores(project)

    # Group files by top-level directory
    files_by_prefix: dict[str, list[str]] = defaultdict(list)
    for file in project.files:
        path = file.relative_path
        if "/" not in path:
            continue  # Skip root-level files
        prefix = PurePosixPath(path).parts[0]
        files_by_prefix[prefix].append(path)

    # Collect facts by prefix
    facts_by_prefix: Counter[str] = Counter()
    for endpoint in project.endpoints:
        prefix = _get_prefix(endpoint.source_path)
        if prefix:
            facts_by_prefix[prefix] += 1
    for model in project.data_models:
        prefix = _get_prefix(model.source_path)
        if prefix:
            facts_by_prefix[prefix] += 1
    for component in project.components:
        prefix = _get_prefix(component.source_path)
        if prefix:
            facts_by_prefix[prefix] += 1
    for config_ref in project.config_refs:
        prefix = _get_prefix(config_ref.source_path)
        if prefix:
            facts_by_prefix[prefix] += 1

    # Collect entrypoints by prefix
    entrypoints_by_prefix: Counter[str] = Counter()
    for entrypoint in project.entrypoints:
        prefix = _get_prefix(entrypoint.source_path)
        if prefix:
            entrypoints_by_prefix[prefix] += 1

    # Compute import cohesion for each prefix
    import_cohesion = _compute_import_cohesion(edges, files_by_prefix)

    # Build candidates
    candidates: list[SubsystemCandidate] = []
    for prefix, files in files_by_prefix.items():
        # Discard weak candidates
        if prefix.lower() in WEAK_PREFIXES:
            continue
        if len(files) < MIN_FILES_FOR_SUBSYSTEM:
            continue

        # Only include runtime-like files in relevance sum
        runtime_files = [f for f in files if is_runtime_like_path(f)]
        if not runtime_files:
            continue

        candidates.append(
            SubsystemCandidate(
                prefix=prefix,
                file_count=len(runtime_files),
                fact_count=facts_by_prefix.get(prefix, 0),
                entrypoint_count=entrypoints_by_prefix.get(prefix, 0),
                relevance_sum=sum(file_scores.get(f, 0) for f in runtime_files),
                import_cohesion=import_cohesion.get(prefix, 0.0),
            )
        )

    return candidates


def _get_prefix(path: str) -> str | None:
    """Get the top-level directory prefix from a path."""
    if "/" not in path:
        return None
    return PurePosixPath(path).parts[0]


def _compute_import_cohesion(
    edges: list[ImportEdge], files_by_prefix: dict[str, list[str]]
) -> dict[str, float]:
    """Compute import cohesion for each prefix.

    Cohesion is the fraction of internal imports (imports within the same prefix)
    that are resolved.
    """
    # Build prefix lookup
    path_to_prefix: dict[str, str] = {}
    for prefix, files in files_by_prefix.items():
        for file in files:
            path_to_prefix[file] = prefix

    # Count internal resolved vs total internal imports
    internal_total: Counter[str] = Counter()
    internal_resolved: Counter[str] = Counter()

    for edge in edges:
        source_prefix = path_to_prefix.get(edge.source_path)
        target_prefix = path_to_prefix.get(edge.target_path)

        # Only count edges where source and target are in the same prefix
        if source_prefix and source_prefix == target_prefix:
            internal_total[source_prefix] += 1
            if edge.resolved:
                internal_resolved[source_prefix] += 1

    # Compute cohesion ratio
    cohesion: dict[str, float] = {}
    for prefix in files_by_prefix:
        total = internal_total.get(prefix, 0)
        if total == 0:
            cohesion[prefix] = 0.5  # Default for no internal imports
        else:
            cohesion[prefix] = internal_resolved.get(prefix, 0) / total

    return cohesion


def _score_candidate(candidate: SubsystemCandidate) -> int:
    """Score a subsystem candidate for article generation.

    Higher scores indicate stronger subsystem boundaries.
    """
    score = 0

    # File count: more files = more substantial
    score += min(candidate.file_count * 2, 20)  # Cap at 20 points

    # Fact density: routes, models, components, config refs
    score += min(candidate.fact_count * 3, 30)  # Cap at 30 points

    # Entrypoints: strong signal of subsystem
    score += min(candidate.entrypoint_count * 5, 15)  # Cap at 15 points

    # Relevance: average relevance score per file
    if candidate.file_count > 0:
        avg_relevance = candidate.relevance_sum / candidate.file_count
        # Normalize to 0-15 range (100 is typical runtime score)
        score += min(int(avg_relevance / 10), 15)

    # Import cohesion: bonus for high cohesion
    score += int(candidate.import_cohesion * 10)

    return score


def _build_structure_article(
    project: ExtractedProject,
    candidate: SubsystemCandidate,
    edges: list[ImportEdge],
    base_budget: int = ARTICLE_TOKEN_BUDGET,
    max_budget: int = ARTICLE_TOKEN_BUDGET,
) -> CompiledArticle:
    """Build a structure article for a subsystem candidate.

    Args:
        project: The extracted project.
        candidate: The subsystem candidate to build an article for.
        edges: Fully resolved import edges.
        base_budget: Base token budget for this article.
        max_budget: Maximum token budget for this article.

    Returns:
        A CompiledArticle for this subsystem.
    """
    from .budgets import compute_local_article_budget

    prefix = candidate.prefix
    name = f"subsystem-{prefix}"
    # Prettify title: replace underscores with spaces, then title case
    pretty_prefix = prefix.replace("_", " ").title()
    title = f"{pretty_prefix} Subsystem"

    # Collect source paths for this subsystem
    source_paths = [
        f.relative_path
        for f in project.files
        if f.relative_path.startswith(f"{prefix}/") and is_runtime_like_path(f.relative_path)
    ]

    # Get file scores for ranking
    file_scores = get_file_scores(project)

    # Build sections with priority
    sections: list[tuple[int, str, list[str]]] = []

    # Summary section (highest priority)
    summary_lines = [f"# {title}", ""]
    entrypoints = [ep for ep in project.entrypoints if ep.source_path.startswith(f"{prefix}/")]
    endpoints = [ep for ep in project.endpoints if ep.source_path.startswith(f"{prefix}/")]
    models = [m for m in project.data_models if m.source_path.startswith(f"{prefix}/")]
    components = [c for c in project.components if c.source_path.startswith(f"{prefix}/")]

    # Code-derived summary (no freeform prose)
    summary_parts = []
    if len(source_paths) > 0:
        summary_parts.append(f"{len(source_paths)} files")
    if endpoints:
        summary_parts.append(f"{len(endpoints)} endpoints")
    if models:
        summary_parts.append(f"{len(models)} models")
    if components:
        summary_parts.append(f"{len(components)} components")
    if summary_parts:
        summary_lines.append(f"Contains: {', '.join(summary_parts)}.")
        summary_lines.append("")

    sections.append((SECTION_PRIORITY["summary"], "summary", summary_lines))

    # Key Files section (ranked by relevance)
    key_files_lines: list[str] = []
    ranked_files = sorted(source_paths, key=lambda p: -file_scores.get(p, 0))[:8]
    if ranked_files:
        key_files_lines.append("## Key Files")
        for path in ranked_files:
            score = file_scores.get(path, 0)
            # Determine reason why file matters
            reasons = []
            if any(ep.source_path == path for ep in entrypoints):
                reasons.append("entry point")
            if any(ep.source_path == path for ep in endpoints):
                reasons.append("routes")
            if any(m.source_path == path for m in models):
                reasons.append("models")
            if any(c.source_path == path for c in components):
                reasons.append("UI")
            if not reasons and score >= 50:
                reasons.append("high relevance")
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            key_files_lines.append(f"- `{path}`{reason_str}")
        key_files_lines.append("")

    sections.append((SECTION_PRIORITY["key_files"], "key_files", key_files_lines))

    # Routes section
    routes_lines: list[str] = []
    if endpoints:
        routes_lines.append("## Routes")
        for ep in sorted(endpoints, key=lambda e: (e.path, e.method))[:10]:
            handler = f" - {ep.handler}" if ep.handler else ""
            routes_lines.append(f"- `{ep.method} {ep.path}`{handler}")
        routes_lines.append("")

    sections.append((SECTION_PRIORITY["routes"], "routes", routes_lines))

    # Models section
    models_lines: list[str] = []
    if models:
        models_lines.append("## Models")
        for model in sorted(models, key=lambda m: m.name)[:10]:
            fields = ", ".join(model.fields[:5]) if model.fields else ""
            suffix = f" ({fields})" if fields else ""
            models_lines.append(f"- `{model.name}`{suffix}")
        models_lines.append("")

    sections.append((SECTION_PRIORITY["models"], "models", models_lines))

    # Components section
    components_lines: list[str] = []
    if components:
        components_lines.append("## Components")
        for comp in sorted(components, key=lambda c: c.name)[:10]:
            props = ", ".join(comp.props[:5]) if comp.props else ""
            suffix = f" (props: {props})" if props else ""
            components_lines.append(f"- `{comp.name}`{suffix}")
        components_lines.append("")

    sections.append((SECTION_PRIORITY["components"], "components", components_lines))

    # Config section
    config_refs = [c for c in project.config_refs if c.source_path.startswith(f"{prefix}/")]
    config_lines: list[str] = []
    if config_refs:
        config_lines.append("## Config")
        seen: set[str] = set()
        for ref in config_refs[:10]:
            if ref.name not in seen:
                seen.add(ref.name)
                config_lines.append(f"- `{ref.name}` ({ref.kind})")
        config_lines.append("")

    sections.append((SECTION_PRIORITY["config"], "config", config_lines))

    # Also Inspect section (change hints)
    also_inspect_lines: list[str] = []
    inspect_paths = _compute_also_inspect_paths(project, prefix, source_paths, edges)
    if inspect_paths:
        also_inspect_lines.append("## Also Inspect")
        also_inspect_lines.append("If you change this area, also inspect:")
        for path in inspect_paths[:5]:
            also_inspect_lines.append(f"- `{path}`")
        also_inspect_lines.append("")

    sections.append((SECTION_PRIORITY["also_inspect"], "also_inspect", also_inspect_lines))

    # Compute local budget based on fact density
    local_fact_count = len(endpoints) + len(models) + len(components) + len(config_refs)
    local_budget = compute_local_article_budget(
        local_file_count=len(source_paths),
        local_fact_count=local_fact_count,
        base_budget=base_budget,
        max_budget=max_budget,
    )

    # Apply budget enforcement with computed budget
    markdown = _enforce_article_budget(sections, budget=local_budget)

    # Use the same inspect_paths for related_paths to align metadata with markdown
    return CompiledArticle(
        name=name,
        title=title,
        kind="structure",
        markdown=markdown,
        source_paths=source_paths,
        related_paths=inspect_paths[:10],
    )


def _compute_also_inspect_paths(
    project: ExtractedProject, prefix: str, source_paths: list[str], edges: list[ImportEdge]
) -> list[str]:
    """Compute paths to inspect when changing this subsystem.

    Sources for also-inspect hints:
    - Resolved import neighbors (external files importing from or imported by this
      subsystem). This includes hot files and entrypoints that have import
      relationships with this subsystem.
    - Files in other subsystems that share the same routes (e.g., same API path
      handled by multiple files)
    - Files in other subsystems that share the same data models
    - Files in other subsystems that share the same config refs

    Only includes runtime-like paths to avoid suggesting test/fixture files.
    """
    source_set = set(source_paths)
    inspect_paths: set[str] = set()

    # Import neighbors (external files importing from or imported by this subsystem)
    for edge in edges:
        if not edge.resolved:
            continue
        if edge.target_path in source_set and edge.source_path not in source_set:
            if is_runtime_like_path(edge.source_path):
                inspect_paths.add(edge.source_path)
        if edge.source_path in source_set and edge.target_path not in source_set:
            if is_runtime_like_path(edge.target_path):
                inspect_paths.add(edge.target_path)

    # Find routes in this subsystem
    subsystem_routes = {ep.path for ep in project.endpoints if ep.source_path.startswith(f"{prefix}/")}

    # Find files sharing routes (in other subsystems, only runtime files)
    for endpoint in project.endpoints:
        if (
            endpoint.path in subsystem_routes
            and not endpoint.source_path.startswith(f"{prefix}/")
            and is_runtime_like_path(endpoint.source_path)
        ):
            inspect_paths.add(endpoint.source_path)

    # Find models in this subsystem
    subsystem_models = {m.name for m in project.data_models if m.source_path.startswith(f"{prefix}/")}

    # Find files sharing models (in other subsystems, only runtime files)
    for model in project.data_models:
        if (
            model.name in subsystem_models
            and not model.source_path.startswith(f"{prefix}/")
            and is_runtime_like_path(model.source_path)
        ):
            inspect_paths.add(model.source_path)

    # Find config refs in this subsystem
    subsystem_configs = {c.name for c in project.config_refs if c.source_path.startswith(f"{prefix}/")}

    # Find files sharing config refs (in other subsystems, only runtime files)
    for config in project.config_refs:
        if (
            config.name in subsystem_configs
            and not config.source_path.startswith(f"{prefix}/")
            and is_runtime_like_path(config.source_path)
        ):
            inspect_paths.add(config.source_path)

    return sorted(inspect_paths)


def _enforce_article_budget(
    sections: list[tuple[int, str, list[str]]], budget: int = ARTICLE_TOKEN_BUDGET
) -> str:
    """Enforce token budget on article sections.

    Sections are collapsed in priority order (lowest priority first) until
    the article fits within the budget.

    Args:
        sections: List of (priority, name, lines) tuples.
        budget: Token budget to enforce (default: ARTICLE_TOKEN_BUDGET).

    Returns:
        Markdown string within the token budget.
    """
    # Sort sections by priority (highest first) for output
    sections_by_priority = sorted(sections, key=lambda x: -x[0])

    def build_markdown(sects: list[tuple[int, str, list[str]]]) -> str:
        lines: list[str] = []
        for _, _, section_lines in sects:
            lines.extend(section_lines)
        return "\n".join(lines)

    # Start with all sections
    included = list(sections_by_priority)
    markdown = build_markdown(included)

    # Remove lowest priority sections until within budget
    while estimate_tokens(markdown) > budget and len(included) > 1:
        # Remove the last section (lowest priority)
        included = included[:-1]
        markdown = build_markdown(included)

    # If still over budget, truncate lines
    if estimate_tokens(markdown) > budget:
        lines = markdown.splitlines()
        kept: list[str] = []
        running = ""
        for line in lines:
            tentative = running + line + "\n"
            if estimate_tokens(tentative) > budget - 20:
                kept.append("...truncated to fit budget...")
                break
            running = tentative
            kept.append(line)
        markdown = "\n".join(kept)

    return markdown


# -----------------------------------------------------------------------------
# Domain Article Generation
# -----------------------------------------------------------------------------


def _extract_domain_name(text: str) -> str | None:
    """Extract a domain name from a string (path, model name, config name).

    Returns the lowercase domain name or None if no meaningful domain found.
    """
    # Skip version-like segments (v1, v2, api/v1, etc.)
    if re.match(r"^v\d+$", text.lower()):
        return None

    # Extract meaningful part from path segments
    text = text.lower()

    # Remove common suffixes/prefixes and underscores
    text = re.sub(r"[_-]?(routes?|handlers?|controllers?|services?|api)[_-]?$", "", text)
    text = re.sub(r"^(api[_-]?|[_-]?api)$", "", text)

    # Clean up trailing/leading underscores
    text = text.strip("_-")

    # Skip if too short or just numbers
    if len(text) < 2 or text.isdigit():
        return None

    return text if text else None


def _extract_domain_from_path(path: str) -> str | None:
    """Extract domain name from a route path like /auth/login -> auth."""
    parts = path.strip("/").split("/")
    for part in parts:
        domain = _extract_domain_name(part)
        if domain:
            return domain
    return None


def _extract_domain_from_filename(filepath: str) -> str | None:
    """Extract domain from a filepath like api/auth.py -> auth.

    Prefers deeper, more specific directory names over top-level directories.
    For web/src/auth/Login.tsx, returns 'auth' not 'web'.
    """
    path = PurePosixPath(filepath)

    # Check directory names, preferring deeper ones (more specific)
    # Skip common top-level directories that aren't domain-specific
    skip_dirs = {"src", "lib", "app", "web", "api", "pkg", "internal", "cmd"}
    parts = list(path.parts[:-1])  # Exclude filename

    # Iterate from deepest to shallowest
    for part in reversed(parts):
        if part.lower() in skip_dirs:
            continue
        domain = _extract_domain_name(part)
        if domain:
            return domain

    # Check filename (without extension)
    stem = path.stem
    # Skip generic filenames
    if stem.lower() in ("index", "main", "app", "server", "routes", "handlers", "utils"):
        return None

    return _extract_domain_name(stem)


def _extract_domain_from_name(name: str) -> str | None:
    """Extract domain from a model/config name like AuthToken -> auth, AUTH_SECRET -> auth."""
    # Handle SCREAMING_SNAKE_CASE (config vars)
    if "_" in name and name.isupper():
        parts = name.split("_")
        for part in parts:
            part_lower = part.lower()
            if part_lower not in ("env", "var", "config", "secret", "key", "token", "expiry"):
                if len(part_lower) >= 2:
                    return part_lower
        return None

    # Split camelCase/PascalCase
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", name)
    if parts:
        # Take the first meaningful part
        first = parts[0].lower()
        if first not in ("base", "abstract", "i", "get", "set", "is", "has"):
            return first
    return None


def _build_domain_articles(
    project: ExtractedProject,
    edges: list[ImportEdge],
    budget: int = ARTICLE_TOKEN_BUDGET,
) -> list[CompiledArticle]:
    """Build domain articles for cross-cutting domains with multi-signal evidence.

    Args:
        project: The extracted project.
        edges: Fully resolved import edges.
        budget: Token budget for domain articles.

    Returns:
        A list of domain articles.
    """
    candidates = _collect_domain_candidates(project, edges)

    # Filter to candidates with enough signal types
    strong_candidates = [c for c in candidates if c.signal_count >= MIN_DOMAIN_FACT_TYPES]

    # Cap at MAX_CANDIDATES_TO_SCORE before scoring
    if len(strong_candidates) > MAX_CANDIDATES_TO_SCORE:
        # Sort by signal count descending
        strong_candidates.sort(key=lambda c: -c.signal_count)
        strong_candidates = strong_candidates[:MAX_CANDIDATES_TO_SCORE]

    # Score and rank candidates
    scored = [(c, _score_domain_candidate(c)) for c in strong_candidates]
    scored.sort(key=lambda x: (-x[1], x[0].name))  # Stable alphabetical tie-break

    # Emit articles for top candidates
    articles: list[CompiledArticle] = []
    for candidate, _score in scored:
        if len(articles) >= MAX_DOMAIN_ARTICLES:
            break
        articles.append(_build_domain_article(project, candidate, edges, budget))

    return articles


def _collect_domain_candidates(
    project: ExtractedProject, edges: list[ImportEdge]
) -> list[DomainCandidate]:
    """Collect candidate domains from various project signals.

    Only considers facts from runtime-like paths to avoid polluting domain
    articles with test fixtures and example code.
    """
    candidates: dict[str, DomainCandidate] = {}

    def get_or_create(name: str) -> DomainCandidate:
        if name not in candidates:
            candidates[name] = DomainCandidate(name=name)
        return candidates[name]

    # Extract from route paths (only runtime files)
    for endpoint in project.endpoints:
        if not is_runtime_like_path(endpoint.source_path):
            continue
        domain = _extract_domain_from_path(endpoint.path)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_ROUTE_PATH)
            candidate.route_paths.append(endpoint.path)

    # Extract from route file names (files containing routes, only runtime files)
    route_files: set[str] = {
        ep.source_path for ep in project.endpoints if is_runtime_like_path(ep.source_path)
    }
    for filepath in route_files:
        domain = _extract_domain_from_filename(filepath)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_ROUTE_FILENAME)
            candidate.route_files.append(filepath)

    # Extract from model names (only runtime files)
    for model in project.data_models:
        if not is_runtime_like_path(model.source_path):
            continue
        domain = _extract_domain_from_name(model.name)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_MODEL_NAME)
            candidate.model_names.append(model.name)

    # Extract from config names (only runtime files)
    for config in project.config_refs:
        if not is_runtime_like_path(config.source_path):
            continue
        domain = _extract_domain_from_name(config.name)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_CONFIG_NAME)
            candidate.config_names.append(config.name)

    # Extract from hot files (files with high import connectivity, only runtime files)
    hot_file_paths = _get_hot_file_paths(edges)
    for filepath in hot_file_paths:
        if not is_runtime_like_path(filepath):
            continue
        domain = _extract_domain_from_filename(filepath)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_HOT_FILENAME)
            candidate.hot_files.append(filepath)

    # Extract from import neighborhood (frequently imported files, only runtime files)
    import_targets = _get_frequently_imported_files(edges)
    for filepath in import_targets:
        if not is_runtime_like_path(filepath):
            continue
        domain = _extract_domain_from_filename(filepath)
        if domain:
            candidate = get_or_create(domain)
            candidate.fact_types.add(FACT_TYPE_IMPORT_FILENAME)
            candidate.import_files.append(filepath)

    return list(candidates.values())


def _get_hot_file_paths(edges: list[ImportEdge]) -> list[str]:
    """Get file paths that are hot (high import indegree or outdegree)."""
    indegree: Counter[str] = Counter()
    outdegree: Counter[str] = Counter()

    for edge in edges:
        if edge.resolved:
            indegree[edge.target_path] += 1
            outdegree[edge.source_path] += 1

    # Consider a file "hot" if it has indegree >= 3 or outdegree >= 5
    hot: set[str] = set()
    for path, count in indegree.items():
        if count >= 3:
            hot.add(path)
    for path, count in outdegree.items():
        if count >= 5:
            hot.add(path)

    return sorted(hot)


def _get_frequently_imported_files(edges: list[ImportEdge]) -> list[str]:
    """Get files that are frequently imported by other files."""
    indegree: Counter[str] = Counter()

    for edge in edges:
        if edge.resolved:
            indegree[edge.target_path] += 1

    # Return files with indegree >= 2
    return [path for path, count in indegree.most_common() if count >= 2]


def _score_domain_candidate(candidate: DomainCandidate) -> int:
    """Score a domain candidate for ranking.

    Tie-break rules (in order):
    1. route-path evidence (strongest)
    2. route-file-name evidence
    3. model/config evidence
    4. stable alphabetical tie-break (handled in sorting)
    """
    score = 0

    # Signal count is the primary factor
    score += candidate.signal_count * 100

    # Tie-break 1: route-path evidence
    if FACT_TYPE_ROUTE_PATH in candidate.fact_types:
        score += 50
    score += len(candidate.route_paths) * 5

    # Tie-break 2: route-file-name evidence
    if FACT_TYPE_ROUTE_FILENAME in candidate.fact_types:
        score += 30
    score += len(candidate.route_files) * 3

    # Tie-break 3: model/config evidence
    if FACT_TYPE_MODEL_NAME in candidate.fact_types:
        score += 20
    score += len(candidate.model_names) * 2

    if FACT_TYPE_CONFIG_NAME in candidate.fact_types:
        score += 15
    score += len(candidate.config_names) * 2

    # Hot files and import files are supporting evidence
    score += len(candidate.hot_files) * 1
    score += len(candidate.import_files) * 1

    return score


def _build_domain_article(
    project: ExtractedProject,
    candidate: DomainCandidate,
    edges: list[ImportEdge],
    budget: int = ARTICLE_TOKEN_BUDGET,
) -> CompiledArticle:
    """Build a domain article for a domain candidate.

    Args:
        project: The extracted project.
        candidate: The domain candidate to build an article for.
        edges: Fully resolved import edges.
        budget: Token budget for this article.

    Returns:
        A CompiledArticle for this domain.
    """
    name = f"domain-{candidate.name}"
    # Prettify title: replace underscores with spaces, then title case
    pretty_name = candidate.name.replace("_", " ").title()
    title = f"{pretty_name} Domain"

    # Build sections with priorities for budget enforcement
    sections: list[tuple[int, str, list[str]]] = []

    # Summary section (highest priority)
    summary_lines = [f"# {title}", ""]
    fact_types_desc = ", ".join(sorted(candidate.fact_types))
    summary_lines.append(f"Cross-cutting domain identified via: {fact_types_desc}.")
    summary_lines.append("")
    sections.append((SECTION_PRIORITY["summary"], "summary", summary_lines))

    # Related routes section
    routes_lines: list[str] = []
    if candidate.route_paths:
        routes_lines.append("## Related Routes")
        for path in sorted(set(candidate.route_paths))[:10]:
            routes_lines.append(f"- `{path}`")
        routes_lines.append("")
    sections.append((SECTION_PRIORITY["routes"], "routes", routes_lines))

    # Related models section
    models_lines: list[str] = []
    if candidate.model_names:
        models_lines.append("## Related Models")
        for model_name in sorted(set(candidate.model_names))[:10]:
            # Find model details
            model = next((m for m in project.data_models if m.name == model_name), None)
            if model:
                fields = ", ".join(model.fields[:5]) if model.fields else ""
                suffix = f" ({fields})" if fields else ""
                models_lines.append(f"- `{model_name}`{suffix} in `{model.source_path}`")
            else:
                models_lines.append(f"- `{model_name}`")
        models_lines.append("")
    sections.append((SECTION_PRIORITY["models"], "models", models_lines))

    # Related components section (only runtime files)
    domain_components = [
        c
        for c in project.components
        if is_runtime_like_path(c.source_path)
        and (
            _extract_domain_from_name(c.name) == candidate.name
            or _extract_domain_from_filename(c.source_path) == candidate.name
        )
    ]
    components_lines: list[str] = []
    if domain_components:
        components_lines.append("## Related Components")
        for comp in sorted(domain_components, key=lambda c: c.name)[:10]:
            props = ", ".join(comp.props[:5]) if comp.props else ""
            suffix = f" (props: {props})" if props else ""
            components_lines.append(f"- `{comp.name}`{suffix} in `{comp.source_path}`")
        components_lines.append("")
    sections.append((SECTION_PRIORITY["components"], "components", components_lines))

    # Related config section
    config_lines: list[str] = []
    if candidate.config_names:
        config_lines.append("## Related Config")
        for config_name in sorted(set(candidate.config_names))[:10]:
            config = next((c for c in project.config_refs if c.name == config_name), None)
            if config:
                config_lines.append(f"- `{config_name}` ({config.kind}) in `{config.source_path}`")
            else:
                config_lines.append(f"- `{config_name}`")
        config_lines.append("")
    sections.append((SECTION_PRIORITY["config"], "config", config_lines))

    # Collect source files for this domain
    source_files: set[str] = set()
    source_files.update(candidate.route_files)
    source_files.update(candidate.hot_files)
    source_files.update(candidate.import_files)

    # Add files containing models for this domain (only runtime files)
    for model in project.data_models:
        if (
            is_runtime_like_path(model.source_path)
            and _extract_domain_from_name(model.name) == candidate.name
        ):
            source_files.add(model.source_path)

    # Add files containing components for this domain (only runtime files)
    for comp in project.components:
        if (
            is_runtime_like_path(comp.source_path)
            and (
                _extract_domain_from_name(comp.name) == candidate.name
                or _extract_domain_from_filename(comp.source_path) == candidate.name
            )
        ):
            source_files.add(comp.source_path)

    # Key files section
    key_files_lines: list[str] = []
    if source_files:
        key_files_lines.append("## Key Files")
        for filepath in sorted(source_files)[:10]:
            key_files_lines.append(f"- `{filepath}`")
        key_files_lines.append("")
    sections.append((SECTION_PRIORITY["key_files"], "key_files", key_files_lines))

    # Compute "Also Inspect" paths for this domain
    source_paths = sorted(source_files)
    inspect_paths = _compute_domain_also_inspect_paths(project, source_paths, edges)

    # Also Inspect section
    also_inspect_lines: list[str] = []
    if inspect_paths:
        also_inspect_lines.append("## Also Inspect")
        also_inspect_lines.append("If you change this domain, also inspect:")
        for path in inspect_paths[:5]:
            also_inspect_lines.append(f"- `{path}`")
        also_inspect_lines.append("")
    sections.append((SECTION_PRIORITY["also_inspect"], "also_inspect", also_inspect_lines))

    # Apply budget enforcement with provided budget
    markdown = _enforce_article_budget(sections, budget=budget)

    return CompiledArticle(
        name=name,
        title=title,
        kind="domain",
        markdown=markdown,
        source_paths=source_paths,
        related_paths=inspect_paths[:10],
    )


def _compute_domain_also_inspect_paths(
    project: ExtractedProject, source_paths: list[str], edges: list[ImportEdge]
) -> list[str]:
    """Compute paths to inspect when changing files in this domain.

    Sources for also-inspect hints:
    - Resolved import neighbors (external files importing from or imported by
      files in this domain)
    - Files that share routes, models, or config with the domain files

    Only includes runtime-like paths to avoid suggesting test/fixture files.
    """
    source_set = set(source_paths)
    inspect_paths: set[str] = set()

    # Import neighbors (external files importing from or imported by domain files)
    for edge in edges:
        if not edge.resolved:
            continue
        if edge.target_path in source_set and edge.source_path not in source_set:
            if is_runtime_like_path(edge.source_path):
                inspect_paths.add(edge.source_path)
        if edge.source_path in source_set and edge.target_path not in source_set:
            if is_runtime_like_path(edge.target_path):
                inspect_paths.add(edge.target_path)

    # Find routes in domain files
    domain_routes = {ep.path for ep in project.endpoints if ep.source_path in source_set}

    # Find files sharing routes (outside domain, only runtime files)
    for endpoint in project.endpoints:
        if (
            endpoint.path in domain_routes
            and endpoint.source_path not in source_set
            and is_runtime_like_path(endpoint.source_path)
        ):
            inspect_paths.add(endpoint.source_path)

    # Find models in domain files
    domain_models = {m.name for m in project.data_models if m.source_path in source_set}

    # Find files sharing models (outside domain, only runtime files)
    for model in project.data_models:
        if (
            model.name in domain_models
            and model.source_path not in source_set
            and is_runtime_like_path(model.source_path)
        ):
            inspect_paths.add(model.source_path)

    # Find config refs in domain files
    domain_configs = {c.name for c in project.config_refs if c.source_path in source_set}

    # Find files sharing config refs (outside domain, only runtime files)
    for config in project.config_refs:
        if (
            config.name in domain_configs
            and config.source_path not in source_set
            and is_runtime_like_path(config.source_path)
        ):
            inspect_paths.add(config.source_path)

    return sorted(inspect_paths)


# -----------------------------------------------------------------------------
# Database Article Generation
# -----------------------------------------------------------------------------


def _build_database_article(
    project: ExtractedProject,
    edges: list[ImportEdge],
    budget: int = DATABASE_TOKEN_BUDGET,
) -> CompiledArticle | None:
    """Build a database article listing all data models.

    This is a special article that doesn't count toward the article cap.
    Only includes models from runtime-like paths.

    Args:
        project: The extracted project.
        edges: Fully resolved import edges.
        budget: Token budget for the database article.

    Returns:
        A CompiledArticle for database/models, or None if no runtime models exist.
    """
    # Filter to only runtime models
    runtime_models = [m for m in project.data_models if is_runtime_like_path(m.source_path)]
    if not runtime_models:
        return None

    name = "database"
    title = "Database Models"

    # Build sections with priorities for budget enforcement
    sections: list[tuple[int, str, list[str]]] = []

    # Summary section (highest priority)
    summary_lines = [f"# {title}", ""]
    summary_lines.append(f"Contains {len(runtime_models)} data models.")
    summary_lines.append("")
    sections.append((SECTION_PRIORITY["summary"], "summary", summary_lines))

    # Group models by source file
    models_by_file: dict[str, list] = defaultdict(list)
    for model in runtime_models:
        models_by_file[model.source_path].append(model)

    # Models section
    models_lines: list[str] = []
    models_lines.append("## Models")
    for model in sorted(runtime_models, key=lambda m: (m.source_path, m.name)):
        fields = ", ".join(model.fields[:8]) if model.fields else ""
        suffix = f" - fields: {fields}" if fields else ""
        kind_str = f" ({model.kind})" if model.kind else ""
        models_lines.append(f"- `{model.name}`{kind_str} in `{model.source_path}`{suffix}")
    models_lines.append("")
    sections.append((SECTION_PRIORITY["models"], "models", models_lines))

    # Key files section
    source_files = sorted(set(m.source_path for m in runtime_models))
    key_files_lines: list[str] = []
    if source_files:
        key_files_lines.append("## Key Files")
        for filepath in source_files[:10]:
            count = len(models_by_file[filepath])
            key_files_lines.append(f"- `{filepath}` ({count} model{'s' if count > 1 else ''})")
        key_files_lines.append("")
    sections.append((SECTION_PRIORITY["key_files"], "key_files", key_files_lines))

    # Compute related paths (files that import from model files or share models)
    related_paths = _compute_domain_also_inspect_paths(project, source_files, edges)

    # Apply budget enforcement with provided budget
    markdown = _enforce_article_budget(sections, budget=budget)

    return CompiledArticle(
        name=name,
        title=title,
        kind="database",
        markdown=markdown,
        source_paths=source_files,
        related_paths=related_paths[:10],
    )
