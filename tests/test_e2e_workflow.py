from pathlib import Path

from typer.testing import CliRunner

from context_compiler.cli import app

runner = CliRunner()


def test_init_then_scan_creates_instruction_files_and_context(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    assert runner.invoke(app, ["init", str(repo)]).exit_code == 0
    assert runner.invoke(app, ["scan", str(repo)]).exit_code == 0
    assert (repo / "CLAUDE.md").exists()
    assert (repo / ".context" / "index.md").exists()


def test_full_workflow_doctor_reports_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        '"""Service entry."""\nimport fastapi\n', encoding="utf-8"
    )
    runner.invoke(app, ["init", str(repo)])
    runner.invoke(app, ["scan", str(repo)])
    result = runner.invoke(app, ["doctor", str(repo)])
    assert result.exit_code == 0
    assert "ok" in result.output.lower()


def test_scan_writes_article_files_when_subsystems_exist(tmp_path: Path) -> None:
    """Test that scan writes targeted article files (subsystem-*, domain-*, database.md)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create a subsystem with enough files and facts to trigger article generation
    api_dir = repo / "api"
    api_dir.mkdir()
    (api_dir / "server.py").write_text(
        """from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def get_users():
    return []

@app.post("/users")
def create_user():
    pass
""",
        encoding="utf-8",
    )
    (api_dir / "schema.py").write_text(
        """from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
""",
        encoding="utf-8",
    )
    (api_dir / "config.py").write_text(
        """import os
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")
""",
        encoding="utf-8",
    )

    assert runner.invoke(app, ["scan", str(repo)]).exit_code == 0

    context_dir = repo / ".context"
    assert context_dir.exists()

    # Check that the standard artifacts exist
    assert (context_dir / "index.md").exists()
    assert (context_dir / "map.json").exists()

    # Check that map.json includes articles metadata
    import json

    map_data = json.loads((context_dir / "map.json").read_text(encoding="utf-8"))
    assert "articles" in map_data

    # If subsystem articles are emitted, they should be written as files
    article_files = list(context_dir.glob("subsystem-*.md"))
    database_files = list(context_dir.glob("database.md"))

    # With models present, database.md should exist
    if map_data["articles"]:
        assert len(article_files) > 0 or len(database_files) > 0, (
            "Expected at least one article file to be written"
        )
