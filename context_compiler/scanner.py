from __future__ import annotations

from pathlib import Path

from .fs_utils import detect_language, is_ignored, parse_gitignore, sha1_bytes
from .models import FrameworkHints, ScanInput, SourceFile


def scan_repository(root: Path) -> ScanInput:
    root = root.resolve()
    patterns = parse_gitignore(root / ".gitignore")
    files = _collect_supported_files(root, patterns)
    hints = _detect_framework_hints(root, files, patterns)
    return ScanInput(root=root, files=files, framework_hints=hints)


def _collect_supported_files(root: Path, patterns: list[str]) -> list[SourceFile]:
    collected: list[SourceFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if is_ignored(rel, patterns):
            continue
        language = detect_language(path)
        if language is None:
            continue
        data = path.read_bytes()
        collected.append(
            SourceFile(
                absolute_path=path,
                relative_path=rel,
                language=language,
                size_bytes=len(data),
                sha1=sha1_bytes(data),
                source_bytes=data,
            )
        )
    return collected


def _detect_framework_hints(
    root: Path,
    files: list[SourceFile],
    patterns: list[str],
) -> FrameworkHints:
    hints = FrameworkHints()
    for package_json in sorted(root.rglob("package.json")):
        rel = package_json.relative_to(root).as_posix()
        if is_ignored(rel, patterns):
            continue
        _append_js_framework_hints(
            hints,
            package_json.read_text(encoding="utf-8", errors="replace"),
        )
    for file in files:
        if file.language == "python":
            source = file.source_bytes.decode("utf-8", errors="replace") if file.source_bytes else file.absolute_path.read_text(encoding="utf-8", errors="replace")
            if "from fastapi" in source or "import fastapi" in source:
                if "fastapi" not in hints.python:
                    hints.python.append("fastapi")
            if "from flask" in source or "import flask" in source:
                if "flask" not in hints.python:
                    hints.python.append("flask")
            if "from django" in source or "import django" in source:
                if "django" not in hints.python:
                    hints.python.append("django")
        if file.language == "go":
            source = file.source_bytes.decode("utf-8", errors="replace") if file.source_bytes else file.absolute_path.read_text(encoding="utf-8", errors="replace")
            if "net/http" in source and "net/http" not in hints.go:
                hints.go.append("net/http")
            if "github.com/gin-gonic/gin" in source and "gin" not in hints.go:
                hints.go.append("gin")
        if file.language == "java":
            source = file.source_bytes.decode("utf-8", errors="replace") if file.source_bytes else file.absolute_path.read_text(encoding="utf-8", errors="replace")
            if "org.springframework" in source or "@SpringBootApplication" in source:
                if "spring" not in hints.java:
                    hints.java.append("spring")
    return hints


def _append_js_framework_hints(hints: FrameworkHints, text: str) -> None:
    for package_name in ("express", "react", "next"):
        if f'"{package_name}"' not in text:
            continue
        if package_name not in hints.javascript:
            hints.javascript.append(package_name)
