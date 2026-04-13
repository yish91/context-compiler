# Contributing

This document describes how to contribute to context-compiler, including development setup, code style, testing practices, and the pull request process.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding Language Support](#adding-language-support)
- [Pull Request Process](#pull-request-process)

## Development Setup

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone <repo>
cd context-compiler

# Install with development dependencies
uv sync --extra dev

# Verify installation
uv run context-compiler --help
uv run pytest -q
```

### IDE Setup

The project uses:

- **Ruff** for linting and formatting
- **pytest** for testing
- Type hints throughout (no strict mypy enforcement yet)

Configure your IDE to use Ruff for Python linting.

## Code Style

### Ruff Configuration

The project uses Ruff with these settings (from `pyproject.toml`):

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
exclude = ["tests/fixtures", ".venv"]
```

### Running Lint

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix
```

### Style Guidelines

**General:**

- Line length: 100 characters
- Use type hints for function signatures
- Prefer `from __future__ import annotations` for forward references

**Imports:**

- Standard library first, then third-party, then local
- Use absolute imports within the package
- Avoid wildcard imports

**Naming:**

- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `SCREAMING_SNAKE_CASE`
- Private functions: `_leading_underscore`

**Docstrings:**

- Module-level docstrings are required
- Function docstrings for public APIs
- Use Google-style docstring format:

```python
def example(param: str) -> int:
    """Short description.

    Longer description if needed.

    Args:
        param: Description of param.

    Returns:
        Description of return value.
    """
```

**Data Classes:**

- Use `@dataclass(slots=True)` for memory efficiency
- Define fields with type hints
- Use `field(default_factory=list)` for mutable defaults

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest -q

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/test_compiler.py

# Specific test function
uv run pytest tests/test_compiler.py::test_hot_files_top_three_match_expected_ranking

# With coverage
uv run pytest --cov=context_compiler
```

### Test Organization

| File | Purpose |
|------|---------|
| `test_compiler.py` | Core compilation, artifact writing, article generation |
| `test_article_builder.py` | Structure and domain article derivation |
| `test_freshness.py` | Staleness detection, manifest handling |
| `test_benchmark_value.py` | Token budget validation, golden snapshots |
| `test_e2e_workflow.py` | CLI integration tests |
| `test_scanner.py` | Repository scanning |
| `test_extractors_*.py` | Fact extraction |
| `test_deep_*.py` | Language-specific deep extraction |
| `test_language_agnostic.py` | Generic language support |

### Test Fixtures

Fixtures are located in `tests/fixtures/`:

| Fixture | Purpose |
|---------|---------|
| `polyglot_repo/` | Multi-language repository for baseline testing |
| `wiki_repo/` | Repository with clear subsystems and domains for article testing |
| `medium_repo/` | Benchmark baseline for token budget validation |

**Creating fixtures:**

- Keep fixtures minimal but representative
- Include enough facts to trigger the behavior being tested
- Avoid large files that slow down tests

### Golden Snapshots

Golden snapshots are located in `tests/golden/`:

| Snapshot | Purpose |
|----------|---------|
| `medium_repo_overview.md` | Expected overview output |
| `medium_repo_architecture.md` | Expected architecture output |
| `wiki_repo_index.md` | Expected index with routing hints |
| `wiki_repo_subsystem_api.md` | Expected structure article |
| `wiki_repo_domain_auth.md` | Expected domain article |

**Updating snapshots:**

When intentionally changing output format:

1. Run tests to see the diff
2. Verify the new output is correct
3. Update the golden file with the new expected output
4. Include snapshot changes in the same commit as the code change

**Reviewing snapshot changes:**

- Always review snapshot diffs carefully in PRs
- Ensure changes are intentional, not regressions
- Check that token budgets are still respected

### Writing Tests

**Test structure:**

```python
def test_descriptive_name_describes_expected_behavior() -> None:
    # Arrange
    project = _create_test_project()
    
    # Act
    result = function_under_test(project)
    
    # Assert
    assert result.field == expected_value
```

**Testing article generation:**

```python
def test_build_articles_emits_structure_pages_for_real_subsystems() -> None:
    repo = (Path(__file__).parent / "fixtures" / "wiki_repo").resolve()
    project = extract_project(scan_repository(repo))

    articles = build_articles(project)
    names = {article.name for article in articles}

    assert "subsystem-api" in names
    assert "subsystem-web" in names
```

**Testing with synthetic data:**

```python
def test_rank_paths_prefers_runtime_code_over_tests() -> None:
    files = [
        SourceFile(Path("api/server.py"), "api/server.py", "python", 1, "a"),
        SourceFile(Path("tests/test_api.py"), "tests/test_api.py", "python", 1, "b"),
    ]
    project = ExtractedProject(root=Path("."), files=files, framework_hints=FrameworkHints())

    ranked = rank_paths(project)

    assert ranked[0] == "api/server.py"
```

## Adding Language Support

### Adding a Generic Language

See [docs/internals.md](internals.md#adding-language-support) for detailed instructions.

**Checklist:**

- [ ] Add suffix mapping to `fs_utils.py`
- [ ] Add Tree-sitter profile to `language_profiles.py`
- [ ] Add test in `test_language_agnostic.py`
- [ ] Verify extraction works on sample files

### Adding a Deep Language Pack

**Checklist:**

- [ ] Create pack file in `language_packs/`
- [ ] Implement `can_handle()` and `extract()` functions
- [ ] Register pack in `extractors/__init__.py`
- [ ] Add framework detection in `scanner.py` if needed
- [ ] Create test file `test_deep_<language>.py`
- [ ] Add fixture files demonstrating patterns
- [ ] Document supported frameworks in README

### Testing Language Support

All language additions require:

1. **Unit tests** for extraction logic
2. **Fixture files** demonstrating the patterns being extracted
3. **Integration test** showing end-to-end compilation works

## Pull Request Process

### Branch Naming

Use descriptive branch names:

- `feat/add-ruby-support`
- `fix/domain-article-dedup`
- `docs/improve-internals`
- `refactor/simplify-relevance-scoring`

### Commit Messages

Write clear, descriptive commit messages:

```
feat: add Ruby deep extraction pack

- Add Ruby language pack with Rails route detection
- Support ActiveRecord model extraction
- Add environment variable detection from ENV[]
```

```
fix: prevent duplicate routes in domain articles

Routes were being counted multiple times when the same path
appeared in multiple files. Now deduplicates by (method, path).
```

### Before Submitting

1. **Run tests:**
   ```bash
   uv run pytest -q
   ```

2. **Run lint:**
   ```bash
   uv run ruff check .
   ```

3. **Update documentation** if changing behavior:
   - README.md for user-facing changes
   - docs/internals.md for implementation changes

4. **Update golden snapshots** if output format changes

5. **Add tests** for new functionality

### Review Process

1. Open a pull request with a clear description
2. Ensure CI checks pass (tests + lint)
3. Address review feedback
4. Squash or rebase as needed before merge

### What Makes a Good PR

- **Focused**: One logical change per PR
- **Tested**: New code has tests, existing tests pass
- **Documented**: README/docs updated if needed
- **Clean**: Lint passes, no debug code
- **Explained**: Clear PR description explaining the change
