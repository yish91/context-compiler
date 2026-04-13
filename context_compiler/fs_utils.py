from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

BUILTIN_DENYLIST: tuple[str, ...] = (
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
)

LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".scala": "scala",
    ".dart": "dart",
    ".lua": "lua",
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".cmd": "cmd",
    ".bat": "cmd",
}


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha1_file(path: Path) -> str:
    return sha1_bytes(path.read_bytes())


def detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix)


def parse_gitignore(gitignore_path: Path) -> list[str]:
    if not gitignore_path.exists():
        return []
    patterns: list[str] = []
    for raw in gitignore_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def is_ignored(relative_path: str, patterns: list[str]) -> bool:
    parts = relative_path.split("/")
    for denied in BUILTIN_DENYLIST:
        if denied in parts:
            return True
    for pattern in patterns:
        pat = pattern.rstrip("/")
        if fnmatch.fnmatch(relative_path, pat):
            return True
        if any(fnmatch.fnmatch(part, pat) for part in parts):
            return True
    return False


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# -----------------------------------------------------------------------------
# Path classification helpers for relevance scoring
# -----------------------------------------------------------------------------

TEST_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "test",
        "tests",
        "spec",
        "specs",
        "__tests__",
        "__test__",
    }
)

FIXTURE_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "fixture",
        "fixtures",
        "mocks",
        "stubs",
        "fakes",
        "__fixtures__",
        "__mocks__",
    }
)

EXAMPLE_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "example",
        "examples",
        "demo",
        "demos",
        "sample",
        "samples",
        "sandbox",
        "playground",
    }
)

GENERATED_PATH_SEGMENTS: frozenset[str] = frozenset(
    {
        "generated",
        "gen",
        "build",
        "dist",
        "out",
        "output",
        "cache",
        ".cache",
        "vendor",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
    }
)


def _path_segments(path: str) -> list[str]:
    """Split a path into its directory and file segments."""
    return path.replace("\\", "/").split("/")


def is_test_like_path(path: str) -> bool:
    """Return True if the path appears to be test code."""
    segments = _path_segments(path)
    # Check directory segments
    for segment in segments[:-1]:
        if segment.lower() in TEST_PATH_SEGMENTS:
            return True
    # Check filename
    filename = segments[-1].lower() if segments else ""
    if filename.startswith("test_") or filename.startswith("test."):
        return True
    if (
        filename.endswith("_test.py")
        or filename.endswith(".test.ts")
        or filename.endswith(".test.tsx")
    ):
        return True
    if filename.endswith(".test.js") or filename.endswith(".test.jsx"):
        return True
    if (
        filename.endswith("_spec.rb")
        or filename.endswith(".spec.ts")
        or filename.endswith(".spec.js")
    ):
        return True
    return False


def is_fixture_like_path(path: str) -> bool:
    """Return True if the path appears to be fixture/mock data."""
    segments = _path_segments(path)
    for segment in segments:
        if segment.lower() in FIXTURE_PATH_SEGMENTS:
            return True
    return False


def is_example_like_path(path: str) -> bool:
    """Return True if the path appears to be example/demo code."""
    segments = _path_segments(path)
    for segment in segments:
        if segment.lower() in EXAMPLE_PATH_SEGMENTS:
            return True
    return False


def is_generated_like_path(path: str) -> bool:
    """Return True if the path appears to be generated/build output."""
    segments = _path_segments(path)
    for segment in segments:
        if segment.lower() in GENERATED_PATH_SEGMENTS:
            return True
    return False


def is_runtime_like_path(path: str) -> bool:
    """Return True if the path appears to be runtime source code (not test/fixture/generated)."""
    return not (
        is_test_like_path(path)
        or is_fixture_like_path(path)
        or is_example_like_path(path)
        or is_generated_like_path(path)
    )
