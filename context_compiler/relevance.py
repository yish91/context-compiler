"""Relevance scoring for file ranking in article generation.

This module provides scoring functions that rank files so that runtime code
outranks tests, fixtures, examples, and generated files. Hot files (high
import indegree/outdegree) and files connected to routes, models, components,
and config receive score boosts.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from .fs_utils import (
    is_example_like_path,
    is_fixture_like_path,
    is_generated_like_path,
    is_test_like_path,
)

# Re-export is_runtime_like_path for article builders to use
from .fs_utils import is_runtime_like_path as is_runtime_like_path  # noqa: F401
from .models import ExtractedProject, ImportEdge

# -----------------------------------------------------------------------------
# Score constants (higher = more relevant)
# -----------------------------------------------------------------------------

# Base scores by path classification
SCORE_RUNTIME: int = 100
SCORE_EXAMPLE: int = 40
SCORE_TEST: int = 30
SCORE_FIXTURE: int = 20
SCORE_GENERATED: int = 10

# Boosts for specific file characteristics
BOOST_ENTRYPOINT: int = 50
BOOST_ROUTE: int = 30
BOOST_MODEL: int = 25
BOOST_COMPONENT: int = 25
BOOST_CONFIG: int = 20

# Hot file boosts (per degree, capped)
BOOST_INDEGREE_PER: int = 3
BOOST_OUTDEGREE_PER: int = 1
BOOST_DEGREE_CAP: int = 30

# Entrypoint-like filenames get a boost
ENTRYPOINT_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "main.go",
        "main.ts",
        "main.tsx",
        "main.js",
        "main.jsx",
        "app.py",
        "app.ts",
        "app.tsx",
        "app.js",
        "app.jsx",
        "server.py",
        "server.ts",
        "server.js",
        "index.ts",
        "index.tsx",
        "index.js",
        "index.jsx",
        "application.py",
        "application.rb",
        "Application.java",
        "manage.py",
        "wsgi.py",
        "asgi.py",
    }
)


@dataclass(slots=True)
class FileScore:
    """Score breakdown for a single file."""

    path: str
    base_score: int
    entrypoint_boost: int
    route_boost: int
    model_boost: int
    component_boost: int
    config_boost: int
    hotness_boost: int

    @property
    def total(self) -> int:
        return (
            self.base_score
            + self.entrypoint_boost
            + self.route_boost
            + self.model_boost
            + self.component_boost
            + self.config_boost
            + self.hotness_boost
        )


def compute_base_score(path: str) -> int:
    """Compute the base score for a path based on its classification."""
    if is_generated_like_path(path):
        return SCORE_GENERATED
    if is_fixture_like_path(path):
        return SCORE_FIXTURE
    if is_test_like_path(path):
        return SCORE_TEST
    if is_example_like_path(path):
        return SCORE_EXAMPLE
    return SCORE_RUNTIME


def compute_entrypoint_boost(path: str, explicit_entrypoint_paths: set[str]) -> int:
    """Compute entrypoint boost for a path."""
    if path in explicit_entrypoint_paths:
        return BOOST_ENTRYPOINT
    filename = PurePosixPath(path).name
    if filename in ENTRYPOINT_NAMES:
        return BOOST_ENTRYPOINT // 2  # Half boost for heuristic entrypoints
    return 0


def compute_hotness_boost(path: str, indegree: dict[str, int], outdegree: dict[str, int]) -> int:
    """Compute hotness boost based on import graph connectivity."""
    in_deg = indegree.get(path, 0)
    out_deg = outdegree.get(path, 0)
    boost = in_deg * BOOST_INDEGREE_PER + out_deg * BOOST_OUTDEGREE_PER
    return min(boost, BOOST_DEGREE_CAP)


def _compute_import_degrees(edges: list[ImportEdge]) -> tuple[dict[str, int], dict[str, int]]:
    """Compute indegree and outdegree dictionaries from resolved import edges."""
    indegree: Counter[str] = Counter()
    outdegree: Counter[str] = Counter()
    for edge in edges:
        if edge.resolved:
            indegree[edge.target_path] += 1
            outdegree[edge.source_path] += 1
    return dict(indegree), dict(outdegree)


def score_files(project: ExtractedProject) -> list[FileScore]:
    """Score all files in the project for relevance ranking.

    Returns a list of FileScore objects, one per file in the project.
    """
    # Collect explicit entrypoint paths
    explicit_entrypoint_paths: set[str] = {ep.source_path for ep in project.entrypoints}

    # Collect paths with routes, models, components, config
    route_paths: set[str] = {ep.source_path for ep in project.endpoints}
    model_paths: set[str] = {m.source_path for m in project.data_models}
    component_paths: set[str] = {c.source_path for c in project.components}
    config_paths: set[str] = {c.source_path for c in project.config_refs}

    # Compute import degrees
    indegree, outdegree = _compute_import_degrees(project.import_edges)

    scores: list[FileScore] = []
    for file in project.files:
        path = file.relative_path
        scores.append(
            FileScore(
                path=path,
                base_score=compute_base_score(path),
                entrypoint_boost=compute_entrypoint_boost(path, explicit_entrypoint_paths),
                route_boost=BOOST_ROUTE if path in route_paths else 0,
                model_boost=BOOST_MODEL if path in model_paths else 0,
                component_boost=BOOST_COMPONENT if path in component_paths else 0,
                config_boost=BOOST_CONFIG if path in config_paths else 0,
                hotness_boost=compute_hotness_boost(path, indegree, outdegree),
            )
        )

    return scores


def rank_paths(project: ExtractedProject) -> list[str]:
    """Rank file paths by relevance, returning them in descending order.

    This is the main entry point for relevance ranking. Runtime code will
    rank above test code, fixtures, examples, and generated files.

    Args:
        project: The extracted project to rank files for.

    Returns:
        A list of relative file paths, sorted by relevance (most relevant first).
    """
    scores = score_files(project)
    # Sort by total score descending, then by path ascending for stability
    scores.sort(key=lambda s: (-s.total, s.path))
    return [s.path for s in scores]


def get_file_scores(project: ExtractedProject) -> dict[str, int]:
    """Get a mapping of file paths to their total relevance scores.

    This is a helper for article builders to access scores without re-ranking.
    """
    scores = score_files(project)
    return {s.path: s.total for s in scores}
