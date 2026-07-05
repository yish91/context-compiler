from pathlib import Path

from context_compiler.models import SourceFile
from context_compiler.script_support.cmd import extract_cmd_facts


def _cmd_file(source: str) -> SourceFile:
    return SourceFile(
        absolute_path=Path("build.cmd"),
        relative_path="build.cmd",
        language="cmd",
        size_bytes=len(source),
        sha1="x",
        source_bytes=source.encode("utf-8"),
    )


def test_extract_cmd_labels_skips_eof_marker() -> None:
    source = ":build\necho building\n:deploy\necho deploying\n:EOF\n"
    facts = extract_cmd_facts(_cmd_file(source))
    names = {symbol.name for symbol in facts["symbols"]}
    kinds = {symbol.kind for symbol in facts["symbols"]}
    assert names == {"build", "deploy"}
    assert "EOF" not in names
    assert kinds == {"label"}


def test_extract_cmd_calls_skips_internal_label_targets() -> None:
    source = ":build\ncall setup.cmd\ncall :build\n"
    facts = extract_cmd_facts(_cmd_file(source))
    targets = {edge.target_path for edge in facts["imports"]}
    assert "setup.cmd" in targets
    assert ":build" not in targets


def test_extract_cmd_env_refs_from_set_and_expansion() -> None:
    source = "set APP_ENV=prod\necho %HOME_DIR%\n"
    facts = extract_cmd_facts(_cmd_file(source))
    config = {ref.name: ref for ref in facts["config_refs"]}
    assert "APP_ENV" in config
    assert "HOME_DIR" in config
    assert config["APP_ENV"].kind == "env"
    assert config["HOME_DIR"].kind == "env"


def test_extract_cmd_env_refs_deduplicates_set_before_expansion() -> None:
    source = "set APP_ENV=prod\necho %APP_ENV%\n"
    facts = extract_cmd_facts(_cmd_file(source))
    names = [ref.name for ref in facts["config_refs"]]
    assert names.count("APP_ENV") == 1


def test_extract_cmd_reads_from_disk_when_source_bytes_absent(tmp_path: Path) -> None:
    path = tmp_path / "run.cmd"
    path.write_text(":start\nset TOKEN=abc\n", encoding="utf-8")
    source_file = SourceFile(
        absolute_path=path,
        relative_path="run.cmd",
        language="cmd",
        size_bytes=path.stat().st_size,
        sha1="x",
    )
    facts = extract_cmd_facts(source_file)
    assert {symbol.name for symbol in facts["symbols"]} == {"start"}
    assert {ref.name for ref in facts["config_refs"]} == {"TOKEN"}
