from typer.testing import CliRunner

from context_compiler.cli import app

runner = CliRunner()


def test_scan_command_exists() -> None:
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "Build .context artifacts" in result.output


def test_init_command_exists() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Write assistant instruction files" in result.output
