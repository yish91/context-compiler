from pathlib import Path

from typer.testing import CliRunner

from context_compiler.cli import app

runner = CliRunner()


def test_init_writes_instruction_files(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# Existing guidance\n", encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "codex.md").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Existing guidance" in content
    assert "<!-- context-compiler:begin -->" in content
    assert "<!-- context-compiler:end -->" in content
    mutated = content.replace("Read `.context/index.md` first.", "BROKEN MANAGED CONTENT")
    (tmp_path / "CLAUDE.md").write_text(mutated, encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    rerun_content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert rerun_content.count("<!-- context-compiler:begin -->") == 1
    assert "BROKEN MANAGED CONTENT" not in rerun_content
    assert "Read `.context/index.md` first." in rerun_content


def test_init_creates_copilot_file_under_github_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert "Read `.context/index.md` first." in content


def test_init_preserves_non_managed_content_on_rerun(tmp_path: Path) -> None:
    existing = (
        "# Existing guidance\n"
        "Some team notes.\n"
        "<!-- context-compiler:begin -->\n"
        "stale managed block\n"
        "<!-- context-compiler:end -->\n"
        "More hand-written notes after.\n"
    )
    (tmp_path / "AGENTS.md").write_text(existing, encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    updated = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "Some team notes." in updated
    assert "More hand-written notes after." in updated
    assert "stale managed block" not in updated
    assert "Read `.context/index.md` first." in updated
    assert updated.count("<!-- context-compiler:begin -->") == 1
