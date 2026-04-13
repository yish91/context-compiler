from pathlib import Path

import typer

from . import __version__
from .artifact_writer import write_artifacts
from .compiler import compile_project
from .extractors import extract_project
from .freshness import assess_scan_status, current_source_hashes
from .instructions import write_instruction_files
from .scanner import scan_repository

app = typer.Typer(help="Compile polyglot repositories into AI context artifacts.")


@app.command("scan")
def scan(repo: Path) -> None:
    """Build .context artifacts."""
    scan_input = scan_repository(repo)
    project = extract_project(scan_input)
    compiled = compile_project(project)
    context_dir = write_artifacts(repo, compiled)
    typer.echo(f"Wrote context artifacts to {context_dir}")


@app.command("init")
def init(repo: Path) -> None:
    """Write assistant instruction files."""
    written = write_instruction_files(repo)
    for path in written:
        typer.echo(f"Updated {path}")


@app.command("doctor")
def doctor(repo: Path) -> None:
    """Validate context artifacts and setup freshness."""
    hashes = current_source_hashes(repo)
    status = assess_scan_status(repo, hashes, compiler_version=__version__)
    if status.is_stale:
        typer.echo(f"stale: {', '.join(status.reasons)}")
        if status.missing_files:
            typer.echo(f"missing: {', '.join(status.missing_files)}")
        typer.echo("run `context-compiler scan` to refresh")
        raise typer.Exit(1)
    typer.echo("ok: context artifacts are up to date")
