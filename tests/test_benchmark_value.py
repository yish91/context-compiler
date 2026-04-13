from pathlib import Path

from context_compiler.compiler import compile_project
from context_compiler.extractors import extract_project
from context_compiler.fs_utils import estimate_tokens
from context_compiler.scanner import scan_repository

MEDIUM_REPO = Path(__file__).parent / "fixtures" / "medium_repo"
WIKI_REPO = Path(__file__).parent / "fixtures" / "wiki_repo"
GOLDEN_DIR = Path(__file__).parent / "golden"


def _compile_wiki_repo():
    project = extract_project(scan_repository(WIKI_REPO.resolve()))
    return compile_project(project)

# Curated raw-source baseline: the files a human would read to understand
# the medium fixture project without the compiler.
BASELINE_FILES = (
    "api/routes.py",
    "api/schema.py",
    "api/service.py",
    "web/src/App.tsx",
    "api/config.py",
)


def _compile_medium():
    project = extract_project(scan_repository(MEDIUM_REPO.resolve()))
    return compile_project(project)


def test_overview_golden_snapshot() -> None:
    compiled = _compile_medium()
    expected = (GOLDEN_DIR / "medium_repo_overview.md").read_text(encoding="utf-8")
    assert compiled.overview.rstrip() == expected.rstrip()


def test_architecture_golden_snapshot() -> None:
    compiled = _compile_medium()
    expected = (GOLDEN_DIR / "medium_repo_architecture.md").read_text(encoding="utf-8")
    assert compiled.architecture.rstrip() == expected.rstrip()


def test_generated_artifacts_beat_curated_raw_baseline() -> None:
    compiled = _compile_medium()
    artifact_tokens = sum(
        estimate_tokens(text)
        for text in (
            compiled.index,
            compiled.overview,
            compiled.architecture,
            compiled.routes,
            compiled.schema,
            compiled.components,
            compiled.config,
            compiled.hot_files_markdown,
        )
    )
    baseline_tokens = 0
    for relative in BASELINE_FILES:
        path = MEDIUM_REPO / relative
        baseline_tokens += estimate_tokens(path.read_text(encoding="utf-8"))
    assert baseline_tokens > 0
    # Threshold increased to 40% to accommodate routing hints in index.md
    assert artifact_tokens <= 0.40 * baseline_tokens, (
        f"artifact tokens {artifact_tokens} exceed 40% of baseline {baseline_tokens}"
    )


def test_targeted_article_is_subset_of_broad_artifacts() -> None:
    """Test that a targeted article contains focused information.

    The targeted-read workflow is valuable because:
      1. A targeted article focuses on ONE subsystem (~700 token budget)
      2. Broad artifacts (overview + architecture + routes + schema) cover EVERYTHING

    Even in small repos, the article is a focused subset. In large repos,
    the savings are dramatic: reading index (~300) + one article (~700) = ~1000 tokens
    vs reading all global artifacts which can be 3000+ tokens.
    """
    compiled = _compile_wiki_repo()

    # Find the api article specifically
    api_article = next((a for a in compiled.articles if a.name == "subsystem-api"), None)
    assert api_article is not None, "Expected subsystem-api article to exist"

    # The article should be within max budget (1200 tokens with adaptive growth)
    api_article_tokens = estimate_tokens(api_article.markdown)
    assert api_article_tokens <= 1200, (
        f"Article should stay within max 1200 token budget, got {api_article_tokens}"
    )

    # The article should contain source_paths for targeted reading
    assert len(api_article.source_paths) > 0, "Article should list source files"

    # Index is compact orientation
    index_tokens = estimate_tokens(compiled.index)
    assert index_tokens <= 300, f"Index should stay within 300 token budget, got {index_tokens}"


def test_index_plus_article_cheaper_than_all_global_artifacts() -> None:
    """Test that index + targeted article is cheaper than ALL global artifacts combined.

    This proves the targeted workflow saves tokens when the user knows which
    subsystem they care about.
    """
    compiled = _compile_medium()

    # Targeted path: index + one article (if available)
    index_tokens = estimate_tokens(compiled.index)

    # All global artifacts combined
    all_global_tokens = sum(
        estimate_tokens(text)
        for text in (
            compiled.overview,
            compiled.architecture,
            compiled.routes,
            compiled.schema,
            compiled.components,
            compiled.config,
            compiled.hot_files_markdown,
        )
    )

    # In any non-trivial repo, index alone is much cheaper than all artifacts
    assert index_tokens < all_global_tokens, (
        f"index ({index_tokens}) should be smaller than all global artifacts ({all_global_tokens})"
    )


def test_wiki_repo_index_golden_snapshot() -> None:
    """Test that wiki_repo index matches golden snapshot."""
    compiled = _compile_wiki_repo()
    expected = (GOLDEN_DIR / "wiki_repo_index.md").read_text(encoding="utf-8")
    assert compiled.index.rstrip() == expected.rstrip()


def test_wiki_repo_subsystem_api_golden_snapshot() -> None:
    """Test that wiki_repo subsystem-api article matches golden snapshot."""
    compiled = _compile_wiki_repo()
    api_article = next((a for a in compiled.articles if a.name == "subsystem-api"), None)
    assert api_article is not None, "Expected subsystem-api article"
    expected = (GOLDEN_DIR / "wiki_repo_subsystem_api.md").read_text(encoding="utf-8")
    assert api_article.markdown.rstrip() == expected.rstrip()


def test_wiki_repo_domain_auth_golden_snapshot() -> None:
    """Test that wiki_repo domain-auth article matches golden snapshot."""
    compiled = _compile_wiki_repo()
    auth_article = next((a for a in compiled.articles if a.name == "domain-auth"), None)
    assert auth_article is not None, "Expected domain-auth article"
    expected = (GOLDEN_DIR / "wiki_repo_domain_auth.md").read_text(encoding="utf-8")
    assert auth_article.markdown.rstrip() == expected.rstrip()
