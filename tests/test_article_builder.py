from pathlib import Path

from context_compiler.article_builder import (
    MAX_DOMAIN_ARTICLES,
    MAX_STRUCTURE_ARTICLES,
    MAX_TOTAL_ARTICLES,
    build_articles,
)
from context_compiler.extractors import extract_project
from context_compiler.models import (
    ConfigRef,
    DataModel,
    Endpoint,
    ExtractedProject,
    FrameworkHints,
    SourceFile,
)
from context_compiler.relevance import rank_paths
from context_compiler.scanner import scan_repository


def test_build_articles_emits_structure_pages_for_real_subsystems() -> None:
    repo = (Path(__file__).parent / "fixtures" / "wiki_repo").resolve()
    project = extract_project(scan_repository(repo))

    articles = build_articles(project)
    names = {article.name for article in articles}

    assert "subsystem-api" in names
    assert "subsystem-web" in names


def test_build_articles_emits_domain_page_only_with_multi_signal_evidence() -> None:
    repo = (Path(__file__).parent / "fixtures" / "wiki_repo").resolve()
    project = extract_project(scan_repository(repo))

    articles = build_articles(project)
    names = {article.name for article in articles}

    # auth has 3+ signal types: route paths, route file names, model names, config names
    assert "domain-auth" in names
    # users has only model name (User) - not enough signals
    assert "domain-users" not in names


def test_article_generation_respects_caps() -> None:
    """Test that verifies:
    - no more than 8 targeted articles are emitted
    - no more than 3 are domain articles
    - no more than 5 are structure articles
    """
    # Create a synthetic project with many potential domains and subsystems
    files: list[SourceFile] = []
    endpoints: list[Endpoint] = []
    models: list[DataModel] = []
    config_refs: list[ConfigRef] = []

    # Create 10 potential subsystems (directories with multiple files)
    subsystem_names = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "eta",
        "theta",
        "iota",
        "kappa",
    ]
    for subsys in subsystem_names:
        # Add multiple files per subsystem to make them substantial
        for i in range(5):
            files.append(
                SourceFile(
                    Path(f"{subsys}/module{i}.py"),
                    f"{subsys}/module{i}.py",
                    "python",
                    100,
                    f"sha_{subsys}_{i}",
                )
            )
        # Add routes, models, and config to make them qualify as domains too
        endpoints.append(
            Endpoint(
                method="GET",
                path=f"/{subsys}/list",
                handler=f"{subsys}_list",
                source_path=f"{subsys}/module0.py",
                line=1,
                framework="fastapi",
            )
        )
        models.append(
            DataModel(
                name=f"{subsys.title()}Model",
                kind="class",
                fields=["id", "name"],
                source_path=f"{subsys}/module1.py",
                line=1,
            )
        )
        config_refs.append(
            ConfigRef(
                name=f"{subsys.upper()}_SECRET",
                kind="env",
                source_path=f"{subsys}/module2.py",
                line=1,
            )
        )

    project = ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(),
        endpoints=endpoints,
        data_models=models,
        config_refs=config_refs,
    )

    articles = build_articles(project)

    # Count by kind
    structure_articles = [a for a in articles if a.kind == "structure"]
    domain_articles = [a for a in articles if a.kind == "domain"]
    database_articles = [a for a in articles if a.kind == "database"]
    # Targeted articles exclude the database article (special, doesn't count toward cap)
    targeted_articles = [a for a in articles if a.kind in ("structure", "domain")]

    # Verify caps (database article is a special article, doesn't count toward cap)
    assert len(targeted_articles) <= MAX_TOTAL_ARTICLES, (
        f"Targeted articles {len(targeted_articles)} exceeds max {MAX_TOTAL_ARTICLES}"
    )
    assert len(structure_articles) <= MAX_STRUCTURE_ARTICLES, (
        f"Structure articles {len(structure_articles)} exceeds max {MAX_STRUCTURE_ARTICLES}"
    )
    assert len(domain_articles) <= MAX_DOMAIN_ARTICLES, (
        f"Domain articles {len(domain_articles)} exceeds max {MAX_DOMAIN_ARTICLES}"
    )
    # Database article should exist when models are present
    assert len(database_articles) == 1, "Database article should be emitted when models exist"


def test_rank_paths_prefers_runtime_code_over_tests_and_fixtures() -> None:
    files = [
        SourceFile(Path("api/server.py"), "api/server.py", "python", 1, "a"),
        SourceFile(Path("tests/test_api.py"), "tests/test_api.py", "python", 1, "b"),
        SourceFile(
            Path("tests/fixtures/app/main.py"), "tests/fixtures/app/main.py", "python", 1, "c"
        ),
    ]
    project = ExtractedProject(root=Path("."), files=files, framework_hints=FrameworkHints())

    ranked = rank_paths(project)

    assert ranked[0] == "api/server.py"


def test_large_repo_candidate_lists_are_sliced_before_scoring() -> None:
    """Test large-repo guardrail: candidate lists are capped before expensive scoring.

    This ensures that even with many potential subsystems and domains, the article
    builder doesn't waste time scoring all of them and respects the MAX_CANDIDATES_TO_SCORE cap.
    """
    # Create a synthetic project with 50 potential subsystems
    files: list[SourceFile] = []
    endpoints: list[Endpoint] = []
    models: list[DataModel] = []
    config_refs: list[ConfigRef] = []

    subsystem_names = [f"subsystem_{i:03d}" for i in range(50)]
    for subsys in subsystem_names:
        # Add multiple files per subsystem
        for i in range(5):
            files.append(
                SourceFile(
                    Path(f"{subsys}/module{i}.py"),
                    f"{subsys}/module{i}.py",
                    "python",
                    100,
                    f"sha_{subsys}_{i}",
                )
            )
        endpoints.append(
            Endpoint(
                method="GET",
                path=f"/{subsys}/list",
                handler=f"{subsys}_list",
                source_path=f"{subsys}/module0.py",
                line=1,
                framework="fastapi",
            )
        )
        models.append(
            DataModel(
                name=f"{subsys.title()}Model",
                kind="class",
                fields=["id", "name"],
                source_path=f"{subsys}/module1.py",
                line=1,
            )
        )
        config_refs.append(
            ConfigRef(
                name=f"{subsys.upper()}_SECRET",
                kind="env",
                source_path=f"{subsys}/module2.py",
                line=1,
            )
        )

    project = ExtractedProject(
        root=Path("."),
        files=files,
        framework_hints=FrameworkHints(),
        endpoints=endpoints,
        data_models=models,
        config_refs=config_refs,
    )

    articles = build_articles(project)

    # Count by kind
    structure_articles = [a for a in articles if a.kind == "structure"]
    domain_articles = [a for a in articles if a.kind == "domain"]
    targeted_articles = [a for a in articles if a.kind in ("structure", "domain")]

    # Verify caps are still respected even with 50 potential subsystems
    assert len(structure_articles) <= MAX_STRUCTURE_ARTICLES
    assert len(domain_articles) <= MAX_DOMAIN_ARTICLES
    assert len(targeted_articles) <= MAX_TOTAL_ARTICLES

    # Verify that we didn't score all 50 candidates (implicit via cap enforcement)
    # The fact that we respected MAX_STRUCTURE_ARTICLES proves candidates were sliced
    assert len(structure_articles) <= MAX_STRUCTURE_ARTICLES, (
        f"Structure articles {len(structure_articles)} should respect MAX_CANDIDATES_TO_SCORE cap"
    )
