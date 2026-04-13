from pathlib import Path

from context_compiler.artifact_writer import write_artifacts
from context_compiler.compiler import compile_project
from context_compiler.extractors import extract_project
from context_compiler.extractors import extract_structure
from context_compiler.fs_utils import estimate_tokens
from context_compiler.models import CompiledArticle, CompiledProject, Entrypoint, ExtractedProject, FrameworkHints, SourceFile
from context_compiler.scanner import scan_repository


def _repo() -> Path:
    return (Path(__file__).parent / "fixtures" / "polyglot_repo").resolve()


def _wiki_repo() -> Path:
    return (Path(__file__).parent / "fixtures" / "wiki_repo").resolve()


def _compile_wiki_repo() -> CompiledProject:
    project = extract_project(scan_repository(_wiki_repo()))
    return compile_project(project)


def test_write_artifacts_creates_expected_context_files(tmp_path: Path) -> None:
    project = extract_project(scan_repository(_repo()))
    compiled = compile_project(project)
    write_artifacts(tmp_path, compiled)
    context_dir = tmp_path / ".context"
    assert (context_dir / "index.md").exists()
    assert (context_dir / "overview.md").exists()
    assert (context_dir / "architecture.md").exists()
    assert (context_dir / "routes.md").exists()
    assert (context_dir / "schema.md").exists()
    assert (context_dir / "components.md").exists()
    assert (context_dir / "config.md").exists()
    assert (context_dir / "hot-files.md").exists()
    assert (context_dir / "map.json").exists()
    assert (context_dir / "manifest.json").exists()
    # Max budget bounds (adaptive budgeting may grow budgets up to these limits)
    max_budgets = {
        "index.md": 300,  # Fixed, never grows
        "overview.md": 1000,
        "architecture.md": 1600,
        "routes.md": 2400,
        "schema.md": 1800,
        "components.md": 1600,
        "config.md": 1000,
        "hot-files.md": 500,
    }
    for name, max_tokens in max_budgets.items():
        assert estimate_tokens((context_dir / name).read_text(encoding="utf-8")) <= max_tokens


def test_hot_files_top_three_match_expected_ranking() -> None:
    project = extract_project(scan_repository(_repo()))
    compiled = compile_project(project)
    top = [hot.path for hot in compiled.hot_files[:3]]
    assert top == [
        "web/src/components/Card.tsx",
        "web/src/config.ts",
        "web/src/routes.ts",
    ]


def test_map_json_has_stable_top_level_keys(tmp_path: Path) -> None:
    import json

    project = extract_project(scan_repository(_repo()))
    compiled = compile_project(project)
    write_artifacts(tmp_path, compiled)
    data = json.loads((tmp_path / ".context" / "map.json").read_text(encoding="utf-8"))
    for key in (
        "metadata",
        "artifacts",
        "files",
        "symbols",
        "edges",
        "endpoints",
        "models",
        "components",
        "config_refs",
        "hot_files",
        "entrypoints",
    ):
        assert key in data


def test_manifest_contains_compiler_version_and_hashes(tmp_path: Path) -> None:
    import json

    project = extract_project(scan_repository(_repo()))
    compiled = compile_project(project)
    write_artifacts(tmp_path, compiled)
    manifest = json.loads((tmp_path / ".context" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compiler_version"]
    assert manifest["source_hashes"]
    assert manifest["artifact_hashes"]
    assert "scan_time" in manifest


def _project_with_entrypoints() -> ExtractedProject:
    return ExtractedProject(
        root=Path("."),
        files=[SourceFile(absolute_path=Path("Application.java"), relative_path="src/main/java/com/example/Application.java", language="java", size_bytes=1, sha1="x", source_bytes=b"class Application {}")],
        framework_hints=FrameworkHints(java=["spring"]),
        entrypoints=[Entrypoint(name="main", kind="application", source_path="src/main/java/com/example/Application.java", line=7, framework="java-generic")],
    )


def _project_without_explicit_entrypoints() -> ExtractedProject:
    return ExtractedProject(
        root=Path("."),
        files=[SourceFile(absolute_path=Path("main.py"), relative_path="main.py", language="python", size_bytes=1, sha1="y", source_bytes=b"def main(): pass")],
        framework_hints=FrameworkHints(),
    )


def test_compile_project_prefers_explicit_entrypoints_but_falls_back_to_heuristics() -> None:
    explicit_compiled = compile_project(_project_with_entrypoints())
    assert explicit_compiled.map_json["entrypoints"][0]["framework"] == "java-generic"

    fallback_compiled = compile_project(_project_without_explicit_entrypoints())
    assert "main.py" in fallback_compiled.architecture


def test_compile_project_resolves_internal_java_imports_from_source_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "App.java").write_text(
        "package com.example;\n"
        "\n"
        "import com.example.users.UserService;\n"
        "\n"
        "public class App {}\n",
        encoding="utf-8",
    )
    users_dir = source_dir / "users"
    users_dir.mkdir()
    (users_dir / "UserService.java").write_text(
        "package com.example.users;\n"
        "\n"
        "public class UserService {}\n",
        encoding="utf-8",
    )

    project = extract_structure(scan_repository(repo))
    compiled = compile_project(project)

    edges = [
        edge
        for edge in compiled.map_json["edges"]
        if edge["source"].endswith("App.java")
    ]
    assert edges == [
        {
            "source": "src/main/java/com/example/App.java",
            "target": "src/main/java/com/example/users/UserService.java",
            "resolved": True,
        }
    ]


def test_write_artifacts_writes_dynamic_article_files(tmp_path: Path) -> None:
    compiled = CompiledProject(
        root=tmp_path,
        compiler_version="test",
        files=[],
        summary="",
        overview="# Overview\n",
        architecture="# Architecture\n",
        routes="# Routes\n",
        schema="# Schema\n",
        components="# Components\n",
        config="# Config\n",
        hot_files_markdown="# Hot Files\n",
        index="# Repository Context\n",
        map_json={},
        hot_files=[],
        articles=[
            CompiledArticle(
                name="subsystem-api",
                title="API",
                kind="structure",
                markdown="# API\n",
                source_paths=["api/server.py"],
                related_paths=["api/schema.py"],
            )
        ],
    )

    context_dir = write_artifacts(tmp_path, compiled)

    assert (context_dir / "subsystem-api.md").exists()


# -----------------------------------------------------------------------------
# Task 5 Tests: Index routing hints, Article content, Database article
# -----------------------------------------------------------------------------


def test_index_includes_targeted_article_routing_hints() -> None:
    compiled = _compile_wiki_repo()
    assert "subsystem-api.md" in compiled.index
    assert "database.md" in compiled.index


def test_structure_article_contains_key_files_and_also_inspect_hints() -> None:
    compiled = _compile_wiki_repo()
    # The api subsystem should have Key Files
    api_article = next(a for a in compiled.articles if a.name == "subsystem-api")
    assert "## Key Files" in api_article.markdown

    # The api and web subsystems share AUTH_SECRET config ref
    # This should trigger Also Inspect in the api article
    # pointing to web/src/config.ts which also uses AUTH_SECRET
    assert "## Also Inspect" in api_article.markdown


def test_database_article_is_emitted_when_models_exist() -> None:
    compiled = _compile_wiki_repo()
    assert any(a.name == "database" for a in compiled.articles)


def test_article_budget_enforcement() -> None:
    """Articles should stay within max token budget (adaptive budgets may grow)."""
    compiled = _compile_wiki_repo()
    for article in compiled.articles:
        tokens = estimate_tokens(article.markdown)
        if article.kind in ("structure", "domain"):
            # Max article budget is 1200 (adaptive can grow from 700 baseline)
            assert tokens <= 1200, f"Article {article.name} exceeds max budget: {tokens} tokens"
        elif article.kind == "database":
            # Max database budget is 1600 (adaptive can grow from 800 baseline)
            assert tokens <= 1600, f"Article {article.name} exceeds max budget: {tokens} tokens"


def test_map_json_includes_article_metadata() -> None:
    """map.json should include article metadata for programmatic access."""
    compiled = _compile_wiki_repo()
    assert "articles" in compiled.map_json

    articles = compiled.map_json["articles"]
    assert len(articles) > 0

    # Each article entry should have the expected keys
    for article in articles:
        assert "name" in article
        assert "title" in article
        assert "kind" in article
        assert "source_paths" in article
        assert "related_paths" in article
        # Should NOT include full markdown in map.json
        assert "markdown" not in article


def test_write_artifacts_cleans_up_orphan_article_files(tmp_path: Path) -> None:
    """Test that orphan article files from previous scans are removed."""
    import json

    context_dir = tmp_path / ".context"
    context_dir.mkdir()

    # Create a previous manifest with an article that won't be regenerated
    (context_dir / "domain-old.md").write_text("# Old Domain\n", encoding="utf-8")
    (context_dir / "manifest.json").write_text(
        json.dumps({
            "compiler_version": "test",
            "scan_time": 0,
            "source_hashes": {},
            "artifact_hashes": {"domain-old.md": "abc"},
            "article_files": ["domain-old.md"],
        }),
        encoding="utf-8",
    )

    # Write new artifacts with a different article
    compiled = CompiledProject(
        root=tmp_path,
        compiler_version="test",
        files=[],
        summary="",
        overview="# Overview\n",
        architecture="# Architecture\n",
        routes="# Routes\n",
        schema="# Schema\n",
        components="# Components\n",
        config="# Config\n",
        hot_files_markdown="# Hot Files\n",
        index="# Repository Context\n",
        map_json={},
        hot_files=[],
        articles=[
            CompiledArticle(
                name="subsystem-new",
                title="New",
                kind="structure",
                markdown="# New\n",
                source_paths=[],
                related_paths=[],
            )
        ],
    )

    write_artifacts(tmp_path, compiled)

    # Old article should be removed
    assert not (context_dir / "domain-old.md").exists()
    # New article should exist
    assert (context_dir / "subsystem-new.md").exists()
