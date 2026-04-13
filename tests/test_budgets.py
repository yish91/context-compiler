"""Tests for adaptive budget configuration and computation."""

from pathlib import Path

from context_compiler.budgets import (
    BudgetSettings,
    compute_budget_profile,
    compute_local_article_budget,
    default_budget_settings,
    load_budget_settings,
)
from context_compiler.models import (
    Component,
    DataModel,
    Endpoint,
    Entrypoint,
    ExtractedProject,
    FrameworkHints,
    ImportEdge,
    SourceFile,
)


# -----------------------------------------------------------------------------
# Config Loading Tests
# -----------------------------------------------------------------------------


def test_load_budget_settings_returns_defaults_when_config_missing(tmp_path: Path) -> None:
    settings = load_budget_settings(tmp_path)
    assert settings.mode == "adaptive"
    assert settings.global_limits.index == 300
    assert settings.global_limits.routes_min == 1200
    assert settings.global_limits.routes_max == 2400


def test_load_budget_settings_returns_defaults_when_pyproject_has_no_budget_section(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\n",
        encoding="utf-8",
    )
    settings = load_budget_settings(tmp_path)
    assert settings.mode == "adaptive"
    assert settings.global_limits.index == 300


def test_load_budget_settings_reads_pyproject_override(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.context-compiler.budgets]\n"
        "mode = 'fixed'\n"
        "[tool.context-compiler.budgets.global]\n"
        "routes_max = 2600\n",
        encoding="utf-8",
    )

    settings = load_budget_settings(tmp_path)

    assert settings.mode == "fixed"
    assert settings.global_limits.routes_max == 2600
    # Other values should be defaults
    assert settings.global_limits.routes_min == 1200
    assert settings.global_limits.index == 300


def test_load_budget_settings_validates_mode(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.context-compiler.budgets]\n"
        "mode = 'invalid'\n",
        encoding="utf-8",
    )
    settings = load_budget_settings(tmp_path)
    assert settings.mode == "adaptive"  # Falls back to default


def test_load_budget_settings_handles_malformed_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "this is not valid [toml",
        encoding="utf-8",
    )
    settings = load_budget_settings(tmp_path)
    assert settings.mode == "adaptive"


def test_default_budget_settings_returns_expected_values() -> None:
    settings = default_budget_settings()
    assert settings.mode == "adaptive"
    assert settings.global_limits.index == 300
    assert settings.global_limits.overview_min == 600
    assert settings.global_limits.overview_max == 1000
    assert settings.article_limits.article_min == 700
    assert settings.article_limits.database_min == 800


# -----------------------------------------------------------------------------
# Budget Profile Computation Tests
# -----------------------------------------------------------------------------


def _empty_project() -> ExtractedProject:
    return ExtractedProject(
        root=Path("."),
        files=[],
        framework_hints=FrameworkHints(),
    )


def _small_project() -> ExtractedProject:
    """A small project with a few files, no special signals."""
    files = [
        SourceFile(
            absolute_path=Path(f"src/file{i}.py"),
            relative_path=f"src/file{i}.py",
            language="python",
            size_bytes=100,
            sha1=f"hash{i}",
        )
        for i in range(5)
    ]
    return ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(),
    )


def _route_dense_project() -> ExtractedProject:
    """A project with many endpoints (>40 to trigger growth)."""
    files = [
        SourceFile(
            absolute_path=Path(f"api/routes{i}.py"),
            relative_path=f"api/routes{i}.py",
            language="python",
            size_bytes=100,
            sha1=f"hash{i}",
        )
        for i in range(10)
    ]
    endpoints = [
        Endpoint(
            method="GET",
            path=f"/api/v1/resource{i}",
            handler=f"get_resource{i}",
            source_path="api/routes0.py",
            line=10 + i,
            framework="fastapi",
        )
        for i in range(45)
    ]
    return ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(python=["fastapi"]),
        endpoints=endpoints,
    )


def _model_dense_project() -> ExtractedProject:
    """A project with many models and fields."""
    files = [
        SourceFile(
            absolute_path=Path(f"models/model{i}.py"),
            relative_path=f"models/model{i}.py",
            language="python",
            size_bytes=100,
            sha1=f"hash{i}",
        )
        for i in range(10)
    ]
    models = [
        DataModel(
            name=f"Model{i}",
            kind="pydantic",
            fields=[f"field{j}" for j in range(6)],
            source_path=f"models/model{i % 10}.py",
            line=10,
            framework="pydantic",
        )
        for i in range(25)
    ]
    return ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(python=["pydantic"]),
        data_models=models,
    )


def _component_dense_project() -> ExtractedProject:
    """A project with many components."""
    files = [
        SourceFile(
            absolute_path=Path(f"components/Component{i}.tsx"),
            relative_path=f"components/Component{i}.tsx",
            language="tsx",
            size_bytes=100,
            sha1=f"hash{i}",
        )
        for i in range(20)
    ]
    components = [
        Component(
            name=f"Component{i}",
            props=[f"prop{j}" for j in range(4)],
            source_path=f"components/Component{i % 20}.tsx",
            line=10,
            framework="react",
        )
        for i in range(35)
    ]
    return ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(javascript=["react"]),
        components=components,
    )


def _large_connected_project() -> ExtractedProject:
    """A large project with many files and import edges."""
    files = [
        SourceFile(
            absolute_path=Path(f"src/{d}/file{i}.py"),
            relative_path=f"src/{d}/file{i}.py",
            language="python",
            size_bytes=100,
            sha1=f"hash{d}{i}",
        )
        for d in ["api", "core", "utils", "services", "models", "handlers", "middleware"]
        for i in range(25)
    ]
    entrypoints = [
        Entrypoint(
            name=f"main{i}",
            kind="application",
            source_path=f"src/api/file{i}.py",
            line=1,
            framework="fastapi",
        )
        for i in range(6)
    ]
    return ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(python=["fastapi"]),
        entrypoints=entrypoints,
    )


def test_compute_budget_profile_keeps_small_project_near_baseline() -> None:
    project = _small_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())
    assert profile.index == 300
    assert profile.overview == 600  # baseline
    assert profile.routes == 1200  # baseline
    assert profile.schema == 900  # baseline
    assert profile.structure_article == 700  # baseline


def test_compute_budget_profile_grows_routes_for_endpoint_dense_project() -> None:
    project = _route_dense_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())
    # 45 endpoints > 40 threshold, should trigger tier 1 and tier 2
    assert profile.routes > 1200
    assert profile.routes <= 2400  # max


def test_compute_budget_profile_grows_schema_for_model_dense_project() -> None:
    project = _model_dense_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())
    # 25 models > 20 threshold, 150 fields > 50 threshold
    assert profile.schema > 900
    assert profile.schema <= 1800  # max
    # Database should also grow
    assert profile.database > 800


def test_compute_budget_profile_grows_components_for_component_dense_project() -> None:
    project = _component_dense_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())
    # 35 components > 30 threshold, 140 props > 50 threshold
    assert profile.components > 800
    assert profile.components <= 1600  # max


def test_compute_budget_profile_grows_architecture_for_connected_project() -> None:
    project = _large_connected_project()
    # Create many resolved edges
    edges = [
        ImportEdge(
            source_path=f"src/api/file{i}.py",
            target_path=f"src/core/file{i}.py",
            raw=f"import core.file{i}",
            resolved=True,
        )
        for i in range(120)
    ]
    profile = compute_budget_profile(project, resolved_edges=edges, settings=default_budget_settings())
    # 120 edges > 100 threshold, 6 entrypoints > 5 threshold
    assert profile.architecture > 900
    assert profile.architecture <= 1600  # max


def test_compute_budget_profile_fixed_mode_returns_baseline() -> None:
    project = _route_dense_project()
    settings = BudgetSettings(mode="fixed")
    profile = compute_budget_profile(project, resolved_edges=[], settings=settings)
    # Fixed mode should not grow
    assert profile.routes == 1200
    assert profile.schema == 900
    assert profile.components == 800


def test_compute_budget_profile_index_always_fixed() -> None:
    project = _large_connected_project()
    edges = [
        ImportEdge(
            source_path=f"src/api/file{i}.py",
            target_path=f"src/core/file{i}.py",
            raw=f"import core.file{i}",
            resolved=True,
        )
        for i in range(200)
    ]
    profile = compute_budget_profile(project, resolved_edges=edges, settings=default_budget_settings())
    # Index should remain fixed at 300
    assert profile.index == 300


def test_compute_budget_profile_respects_configured_max() -> None:
    project = _route_dense_project()
    settings = BudgetSettings()
    settings.global_limits.routes_max = 1400  # Lower max
    profile = compute_budget_profile(project, resolved_edges=[], settings=settings)
    # Should be clamped to configured max
    assert profile.routes <= 1400


def test_compute_budget_profile_respects_configured_min() -> None:
    project = _empty_project()
    settings = BudgetSettings()
    settings.global_limits.routes_min = 1500  # Higher min
    profile = compute_budget_profile(project, resolved_edges=[], settings=settings)
    # Should be at least the configured min
    assert profile.routes >= 1500


# -----------------------------------------------------------------------------
# Local Article Budget Tests
# -----------------------------------------------------------------------------


def test_compute_local_article_budget_no_growth_for_small_subsystem() -> None:
    budget = compute_local_article_budget(
        local_file_count=5,
        local_fact_count=2,
        base_budget=700,
        max_budget=1200,
    )
    assert budget == 700  # No growth


def test_compute_local_article_budget_grows_for_dense_subsystem() -> None:
    budget = compute_local_article_budget(
        local_file_count=15,
        local_fact_count=10,
        base_budget=700,
        max_budget=1200,
    )
    assert budget > 700
    assert budget <= 1200


def test_compute_local_article_budget_clamped_to_max() -> None:
    budget = compute_local_article_budget(
        local_file_count=50,
        local_fact_count=100,
        base_budget=700,
        max_budget=900,
    )
    assert budget == 900  # Clamped to max


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


def test_budget_profile_is_deterministic() -> None:
    """Budget computation should be deterministic for the same input."""
    project = _route_dense_project()
    settings = default_budget_settings()
    edges: list[ImportEdge] = []

    profile1 = compute_budget_profile(project, edges, settings)
    profile2 = compute_budget_profile(project, edges, settings)

    assert profile1.routes == profile2.routes
    assert profile1.schema == profile2.schema
    assert profile1.components == profile2.components
    assert profile1.architecture == profile2.architecture


def test_empty_project_uses_baseline_budgets() -> None:
    """Empty project should use baseline budgets."""
    project = _empty_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())
    assert profile.index == 300
    assert profile.overview == 600
    assert profile.architecture == 900
    assert profile.routes == 1200
    assert profile.schema == 900
    assert profile.components == 800
    assert profile.config == 500
    assert profile.hot_files == 300


def test_budget_profile_includes_max_bounds_for_local_growth() -> None:
    """Budget profile should include max bounds for local article growth."""
    project = _small_project()
    profile = compute_budget_profile(project, resolved_edges=[], settings=default_budget_settings())

    # Max bounds should be included in profile
    assert profile.structure_article_max == 1200
    assert profile.database_max == 1600

    # Max bounds should be greater than or equal to computed budgets
    assert profile.structure_article_max >= profile.structure_article
    assert profile.database_max >= profile.database
