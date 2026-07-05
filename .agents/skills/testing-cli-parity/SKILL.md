---
name: testing-cli-parity
description: Test context-compiler end-to-end and prove behavior-preserving refactors. Use when verifying CLI output or refactor PRs that should not change behavior.
---

# Testing context-compiler (CLI)

`context-compiler` is a deterministic CLI that scans a repo and writes `.context/` artifacts (markdown + `map.json` + `manifest.json`).

## Setup / running
- Install/run with `uv`: `uv sync --extra dev`, then run via the console script: `uv run context-compiler <cmd> <repo>`.
- IMPORTANT: the entrypoint is the console script `context-compiler = context_compiler.cli:app`. Do NOT invoke `python -m context_compiler.cli` — cli.py has no `__main__` guard, so it silently does nothing (exit 0, no output, no artifacts).
- Commands: `scan <repo>` writes artifacts; `doctor <repo>` checks freshness (exit 0 = fresh); `init <repo>` writes assistant instruction files.
- Fixture repos live in `tests/fixtures/` (deep_{go,java,python,ts}_repo, medium_repo, multilang_repo, polyglot_repo, script_repo, wiki_repo). Good, varied inputs for exercising all extractors/language packs.

## Proving a behavior-preserving refactor (parity test)
Best end-to-end proof that a refactor didn't change behavior: run the CLI with pre-refactor code (a `git worktree add /tmp/cc-main origin/main`) vs the PR branch on each fixture, then `diff -r` the two `.context/` dirs.

- Scan writes `.context/` INTO the target repo dir, so copy each fixture into two separate temp dirs and scan each with the respective code version.
- **Volatile fields will always differ — normalize them before diffing** (they are non-deterministic, not regressions):
  - `map.json` → `"repo_root"` (absolute path of the scanned dir)
  - `map.json` + `manifest.json` → `"scan_time"` (wall-clock unix ts; can differ by 1s between runs)
  - `manifest.json` → the `"map.json"` hash entry (content hash derived from `map.json`, so it changes when repo_root/scan_time do)
  - `sed` these to constants, then diff. Remaining diff should be empty for a true refactor.
- This is a shell-only test → do NOT record; collect command output as text evidence.

## Regression suite
- `uv run pytest -q` (expect `96 passed` as of this writing; count may grow) and `uv run ruff check .` (expect `All checks passed!`).

## Devin Secrets Needed
None. Public repo, local-only CLI, no external services or credentials.
