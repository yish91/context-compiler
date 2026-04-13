"""Adaptive budget configuration and computation for context-compiler.

This module provides:
- Budget configuration dataclasses
- Default policy values
- pyproject.toml loading
- Stepwise budget profile computation based on fact density

Budget profiles are computed after extraction and import resolution,
then used by the compiler and article builder instead of fixed constants.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ExtractedProject, ImportEdge


# -----------------------------------------------------------------------------
# Configuration Dataclasses
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class GlobalBudgetLimits:
    """Min/max bounds for global artifact budgets."""

    index: int = 300  # Fixed, never grows
    overview_min: int = 600
    overview_max: int = 1000
    architecture_min: int = 900
    architecture_max: int = 1600
    routes_min: int = 1200
    routes_max: int = 2400
    schema_min: int = 900
    schema_max: int = 1800
    components_min: int = 800
    components_max: int = 1600
    config_min: int = 500
    config_max: int = 1000
    hot_files_min: int = 300
    hot_files_max: int = 500


@dataclass(slots=True)
class ArticleBudgetLimits:
    """Min/max bounds for targeted article budgets."""

    article_min: int = 700
    article_max: int = 1200
    database_min: int = 800
    database_max: int = 1600


@dataclass(slots=True)
class BudgetSettings:
    """Budget configuration loaded from pyproject.toml."""

    mode: str = "adaptive"  # "adaptive" or "fixed"
    global_limits: GlobalBudgetLimits = field(default_factory=GlobalBudgetLimits)
    article_limits: ArticleBudgetLimits = field(default_factory=ArticleBudgetLimits)


# -----------------------------------------------------------------------------
# Budget Profile (computed budgets for a specific project)
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class BudgetProfile:
    """Computed budgets for a specific project based on fact density."""

    # Global artifact budgets
    index: int = 300
    overview: int = 600
    architecture: int = 900
    routes: int = 1200
    schema: int = 900
    components: int = 800
    config: int = 500
    hot_files: int = 300

    # Article budgets
    structure_article: int = 700
    domain_article: int = 700
    database: int = 800

    # Max bounds for local article growth
    structure_article_max: int = 1200
    database_max: int = 1600


# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------


def default_budget_settings() -> BudgetSettings:
    """Return the default budget settings."""
    return BudgetSettings()


# -----------------------------------------------------------------------------
# Configuration Loading
# -----------------------------------------------------------------------------


def load_budget_settings(repo_root: Path) -> BudgetSettings:
    """Load budget settings from pyproject.toml.

    Falls back to defaults when config is missing or incomplete.
    Partial overrides are supported: missing keys use default values.

    Args:
        repo_root: Path to the repository root.

    Returns:
        BudgetSettings with any pyproject.toml overrides applied.
    """
    pyproject_path = repo_root / "pyproject.toml"

    if not pyproject_path.exists():
        return default_budget_settings()

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return default_budget_settings()

    budget_config = data.get("tool", {}).get("context-compiler", {}).get("budgets", {})
    if not budget_config:
        return default_budget_settings()

    # Parse mode
    mode = budget_config.get("mode", "adaptive")
    if mode not in ("adaptive", "fixed"):
        mode = "adaptive"

    # Parse global limits
    global_config = budget_config.get("global", {})
    defaults = GlobalBudgetLimits()
    global_limits = GlobalBudgetLimits(
        index=global_config.get("index", defaults.index),
        overview_min=global_config.get("overview_min", defaults.overview_min),
        overview_max=global_config.get("overview_max", defaults.overview_max),
        architecture_min=global_config.get("architecture_min", defaults.architecture_min),
        architecture_max=global_config.get("architecture_max", defaults.architecture_max),
        routes_min=global_config.get("routes_min", defaults.routes_min),
        routes_max=global_config.get("routes_max", defaults.routes_max),
        schema_min=global_config.get("schema_min", defaults.schema_min),
        schema_max=global_config.get("schema_max", defaults.schema_max),
        components_min=global_config.get("components_min", defaults.components_min),
        components_max=global_config.get("components_max", defaults.components_max),
        config_min=global_config.get("config_min", defaults.config_min),
        config_max=global_config.get("config_max", defaults.config_max),
        hot_files_min=global_config.get("hot_files_min", defaults.hot_files_min),
        hot_files_max=global_config.get("hot_files_max", defaults.hot_files_max),
    )

    # Parse article limits
    article_config = budget_config.get("articles", {})
    article_defaults = ArticleBudgetLimits()
    article_limits = ArticleBudgetLimits(
        article_min=article_config.get("article_min", article_defaults.article_min),
        article_max=article_config.get("article_max", article_defaults.article_max),
        database_min=article_config.get("database_min", article_defaults.database_min),
        database_max=article_config.get("database_max", article_defaults.database_max),
    )

    return BudgetSettings(
        mode=mode,
        global_limits=global_limits,
        article_limits=article_limits,
    )


# -----------------------------------------------------------------------------
# Stepwise Growth Helpers
# -----------------------------------------------------------------------------


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def _stepwise_budget(
    base: int,
    step_size: int,
    *conditions: bool,
    min_budget: int,
    max_budget: int,
) -> int:
    """Compute a stepwise budget based on triggered conditions.

    Each True condition adds one step_size to the base.

    Args:
        base: Starting budget value.
        step_size: Amount to add per triggered condition.
        *conditions: Boolean conditions that each add one tier.
        min_budget: Minimum allowed budget.
        max_budget: Maximum allowed budget.

    Returns:
        The computed budget, clamped to [min_budget, max_budget].
    """
    tiers = sum(1 for c in conditions if c)
    budget = base + (step_size * tiers)
    return _clamp(budget, min_budget, max_budget)


# -----------------------------------------------------------------------------
# Signal Extraction Helpers
# -----------------------------------------------------------------------------


def _count_runtime_files(project: "ExtractedProject") -> int:
    """Count runtime-like files in the project."""
    from .fs_utils import is_runtime_like_path

    return sum(1 for f in project.files if is_runtime_like_path(f.relative_path))


def _count_top_level_dirs(project: "ExtractedProject") -> int:
    """Count distinct top-level directories with runtime files."""
    from .fs_utils import is_runtime_like_path

    dirs: set[str] = set()
    for f in project.files:
        if not is_runtime_like_path(f.relative_path):
            continue
        if "/" in f.relative_path:
            dirs.add(f.relative_path.split("/")[0])
    return len(dirs)


def _count_resolved_edges(edges: list["ImportEdge"]) -> int:
    """Count resolved import edges."""
    return sum(1 for e in edges if e.resolved)


def _count_entrypoints(project: "ExtractedProject") -> int:
    """Count explicit entrypoints."""
    return len(project.entrypoints)


def _count_endpoints(project: "ExtractedProject") -> int:
    """Count extracted endpoints."""
    return len(project.endpoints)


def _count_models(project: "ExtractedProject") -> int:
    """Count data models."""
    return len(project.data_models)


def _count_total_fields(project: "ExtractedProject") -> int:
    """Count total fields across all models."""
    return sum(len(m.fields) for m in project.data_models)


def _count_components(project: "ExtractedProject") -> int:
    """Count UI components."""
    return len(project.components)


def _count_total_props(project: "ExtractedProject") -> int:
    """Count total props across all components."""
    return sum(len(c.props) for c in project.components)


def _count_config_refs(project: "ExtractedProject") -> int:
    """Count unique config references."""
    return len({c.name for c in project.config_refs})


# -----------------------------------------------------------------------------
# Budget Profile Computation
# -----------------------------------------------------------------------------


def compute_budget_profile(
    project: "ExtractedProject",
    resolved_edges: list["ImportEdge"],
    settings: BudgetSettings,
) -> BudgetProfile:
    """Compute a budget profile for the project based on fact density.

    In fixed mode, returns baseline budgets matching current behavior.
    In adaptive mode, grows budgets based on artifact-specific signals.

    Args:
        project: The extracted project.
        resolved_edges: Fully resolved import edges.
        settings: Budget configuration settings.

    Returns:
        A BudgetProfile with computed budgets for all artifacts.
    """
    limits = settings.global_limits
    article_limits = settings.article_limits

    # Fixed mode: return baseline budgets
    if settings.mode == "fixed":
        return BudgetProfile(
            index=300,
            overview=limits.overview_min,
            architecture=limits.architecture_min,
            routes=limits.routes_min,
            schema=limits.schema_min,
            components=limits.components_min,
            config=limits.config_min,
            hot_files=limits.hot_files_min,
            structure_article=article_limits.article_min,
            domain_article=article_limits.article_min,
            database=article_limits.database_min,
            structure_article_max=article_limits.article_max,
            database_max=article_limits.database_max,
        )

    # Adaptive mode: compute based on signals
    # Extract all signals first
    runtime_files = _count_runtime_files(project)
    top_level_dirs = _count_top_level_dirs(project)
    resolved_count = _count_resolved_edges(resolved_edges)
    entrypoint_count = _count_entrypoints(project)
    endpoint_count = _count_endpoints(project)
    model_count = _count_models(project)
    total_fields = _count_total_fields(project)
    component_count = _count_components(project)
    total_props = _count_total_props(project)
    config_count = _count_config_refs(project)

    # overview.md: grows based on file count and directory count
    # Tiers: 50+ files, 100+ files, 5+ dirs
    # Bonus tier: large repo (150+ files) with many dirs (7+)
    overview = _stepwise_budget(
        limits.overview_min,
        100,  # step size
        runtime_files > 50,
        runtime_files > 100,
        top_level_dirs >= 5,
        runtime_files > 150 and top_level_dirs >= 7,  # bonus tier
        min_budget=limits.overview_min,
        max_budget=limits.overview_max,
    )

    # architecture.md: grows based on import edges and entrypoints
    # Tiers: 50+ edges, 100+ edges, 5+ entrypoints
    # Bonus tier: large repo (150+ files) with high connectivity (100+ edges)
    architecture = _stepwise_budget(
        limits.architecture_min,
        150,  # step size
        resolved_count > 50,
        resolved_count > 100,
        entrypoint_count >= 5,
        runtime_files > 150 and resolved_count > 100,  # bonus tier
        min_budget=limits.architecture_min,
        max_budget=limits.architecture_max,
    )

    # routes.md: grows based on endpoint count
    # Tiers: 20+ endpoints, 40+ endpoints, 80+ endpoints
    # Bonus tier: large repo (150+ files) with 40+ endpoints
    routes = _stepwise_budget(
        limits.routes_min,
        300,  # step size
        endpoint_count > 20,
        endpoint_count > 40,
        endpoint_count > 80,
        runtime_files > 150 and endpoint_count > 40,  # bonus tier
        min_budget=limits.routes_min,
        max_budget=limits.routes_max,
    )

    # schema.md: grows based on model count and field count
    # Tiers: 10+ models, 20+ models, 50+ fields
    # Bonus tier: 30+ models with 100+ fields
    schema = _stepwise_budget(
        limits.schema_min,
        200,  # step size
        model_count > 10,
        model_count > 20,
        total_fields > 50,
        model_count > 30 and total_fields > 100,  # bonus tier
        min_budget=limits.schema_min,
        max_budget=limits.schema_max,
    )

    # components.md: grows based on component count and prop count
    # Tiers: 15+ components, 30+ components, 50+ props
    # Bonus tier: 50+ components with 100+ props
    components = _stepwise_budget(
        limits.components_min,
        200,  # step size
        component_count > 15,
        component_count > 30,
        total_props > 50,
        component_count > 50 and total_props > 100,  # bonus tier
        min_budget=limits.components_min,
        max_budget=limits.components_max,
    )

    # config.md: grows based on unique config ref count
    # Tiers: 10+ refs, 20+ refs, 40+ refs
    config = _stepwise_budget(
        limits.config_min,
        100,  # step size
        config_count > 10,
        config_count > 20,
        config_count > 40,
        min_budget=limits.config_min,
        max_budget=limits.config_max,
    )

    # hot-files.md: conservative growth
    # Tiers: 100+ edges, 200+ edges
    hot_files = _stepwise_budget(
        limits.hot_files_min,
        50,  # small step size
        resolved_count > 100,
        resolved_count > 200,
        min_budget=limits.hot_files_min,
        max_budget=limits.hot_files_max,
    )

    # Structure/domain article budgets: grow based on overall project density
    # Tiers: 100+ files with 10+ models, 150+ files with 20+ endpoints
    article_budget = _stepwise_budget(
        article_limits.article_min,
        150,  # step size
        runtime_files > 100 and model_count > 10,
        runtime_files > 150 and endpoint_count > 20,
        min_budget=article_limits.article_min,
        max_budget=article_limits.article_max,
    )

    # Database article: grows based on model density
    # Tiers: 15+ models, 30+ models, 80+ fields
    database = _stepwise_budget(
        article_limits.database_min,
        200,  # step size
        model_count > 15,
        model_count > 30,
        total_fields > 80,
        min_budget=article_limits.database_min,
        max_budget=article_limits.database_max,
    )

    return BudgetProfile(
        index=300,  # Always fixed
        overview=overview,
        architecture=architecture,
        routes=routes,
        schema=schema,
        components=components,
        config=config,
        hot_files=hot_files,
        structure_article=article_budget,
        domain_article=article_budget,
        database=database,
        structure_article_max=article_limits.article_max,
        database_max=article_limits.database_max,
    )


# -----------------------------------------------------------------------------
# Per-Article Local Budget Computation
# -----------------------------------------------------------------------------


def compute_local_article_budget(
    local_file_count: int,
    local_fact_count: int,
    base_budget: int,
    max_budget: int,
) -> int:
    """Compute a budget for a specific article based on local fact density.

    This is used by the article builder to give denser subsystems more space.

    Args:
        local_file_count: Number of runtime files in the subsystem.
        local_fact_count: Number of facts (routes, models, components, config) in the subsystem.
        base_budget: The baseline budget from the profile.
        max_budget: The maximum allowed budget.

    Returns:
        The computed local budget, clamped to [base_budget, max_budget].
    """
    # Local growth tiers: 10+ files with 5+ facts, 20+ files with 15+ facts
    extra = 0
    if local_file_count >= 10 and local_fact_count >= 5:
        extra += 100
    if local_file_count >= 20 and local_fact_count >= 15:
        extra += 100

    return _clamp(base_budget + extra, base_budget, max_budget)
