from pathlib import Path

from context_compiler.fs_utils import (
    detect_language,
    estimate_tokens,
    is_example_like_path,
    is_fixture_like_path,
    is_generated_like_path,
    is_ignored,
    is_runtime_like_path,
    is_test_like_path,
    parse_gitignore,
    sha1_bytes,
    sha1_file,
)


def test_sha1_bytes_and_file_agree(tmp_path: Path) -> None:
    data = b"hello world"
    path = tmp_path / "data.txt"
    path.write_bytes(data)
    assert sha1_file(path) == sha1_bytes(data)


def test_detect_language_by_suffix() -> None:
    assert detect_language(Path("a.py")) == "python"
    assert detect_language(Path("a.tsx")) == "tsx"
    assert detect_language(Path("a.unknownext")) is None


def test_estimate_tokens_minimum_is_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("12345678") == 2


def test_parse_gitignore_skips_comments_and_blanks(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "# a comment\n\n*.log\n  \nbuild/\n",
        encoding="utf-8",
    )
    assert parse_gitignore(gitignore) == ["*.log", "build/"]


def test_parse_gitignore_missing_file(tmp_path: Path) -> None:
    assert parse_gitignore(tmp_path / "nope.gitignore") == []


def test_is_ignored_matches_builtin_denylist() -> None:
    assert is_ignored("node_modules/pkg/index.js", [])
    assert is_ignored("src/__pycache__/mod.pyc", [])


def test_is_ignored_matches_full_relative_path_pattern() -> None:
    assert is_ignored("logs/output.log", ["logs/output.log"])


def test_is_ignored_matches_segment_pattern() -> None:
    # Pattern matches a path segment but not the full relative path,
    # exercising the per-segment fnmatch fallback.
    assert is_ignored("src/app/secret.env", ["secret.env"])


def test_is_ignored_returns_false_when_no_match() -> None:
    assert not is_ignored("src/app/main.py", ["*.log"])


def test_is_test_like_path_variants() -> None:
    assert is_test_like_path("tests/test_thing.py")
    assert is_test_like_path("test.js")
    assert is_test_like_path("pkg/thing_test.py")
    assert is_test_like_path("web/Button.test.tsx")
    assert is_test_like_path("web/Button.test.js")
    assert is_test_like_path("spec/thing_spec.rb")
    assert is_test_like_path("web/thing.spec.ts")
    assert not is_test_like_path("src/main.py")


def test_is_fixture_and_example_like_paths() -> None:
    assert is_fixture_like_path("tests/fixtures/data.json")
    assert is_example_like_path("examples/demo/app.py")
    assert not is_fixture_like_path("src/app.py")


def test_is_generated_like_path() -> None:
    assert is_generated_like_path("dist/bundle.js")
    assert is_generated_like_path("vendor/lib/thing.go")
    assert not is_generated_like_path("src/app.py")


def test_is_runtime_like_path_excludes_non_runtime() -> None:
    assert is_runtime_like_path("src/service.py")
    assert not is_runtime_like_path("tests/test_service.py")
    assert not is_runtime_like_path("dist/bundle.js")
