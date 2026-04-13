from pathlib import Path


def test_readme_mentions_phase1_deep_support_languages() -> None:
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8").lower()
    assert "typescript" in readme and "tsx" in readme
    assert "python" in readme
    assert "go" in readme
    assert "java" in readme
    assert "generic structural support" in readme


def test_readme_documents_targeted_read_workflow() -> None:
    """README should document the targeted-read workflow and article outputs."""
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    readme_lower = readme.lower()

    # Should describe the targeted-read workflow
    assert "targeted" in readme_lower, "README should mention targeted articles/workflow"
    assert "index" in readme_lower, "README should mention index.md"

    # Should mention article outputs
    assert "subsystem" in readme_lower, "README should mention structure/subsystem articles"
    assert "domain" in readme_lower, "README should mention domain articles"
    assert "database" in readme_lower, "README should mention database article"

    # Should distinguish between broad and targeted artifacts
    assert "broad" in readme_lower or "global" in readme_lower, (
        "README should distinguish broad/global artifacts from targeted articles"
    )


def test_readme_documents_adaptive_budgeting() -> None:
    """README should document adaptive budgeting behavior."""
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    readme_lower = readme.lower()

    # Should mention adaptive budgeting
    assert "adaptive" in readme_lower, "README should mention adaptive budgeting"

    # Should mention pyproject.toml configuration
    assert "pyproject.toml" in readme_lower, "README should mention pyproject.toml for config"

    # Should mention index.md stays fixed
    assert "300" in readme, "README should mention index.md token budget"


def test_internals_documents_adaptive_budgeting() -> None:
    """internals.md should document the adaptive budgeting algorithm."""
    internals = (Path(__file__).parent.parent / "docs" / "internals.md").read_text(encoding="utf-8")
    internals_lower = internals.lower()

    # Should document adaptive budgeting
    assert "adaptive" in internals_lower, "internals.md should mention adaptive budgeting"

    # Should mention budget computation or profile
    assert "budget" in internals_lower, "internals.md should document budget computation"

    # Should mention stepwise growth or tiers
    assert "tier" in internals_lower or "step" in internals_lower, (
        "internals.md should mention stepwise/tiered growth"
    )
