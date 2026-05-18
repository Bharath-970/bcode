# bcode — Phase 1 Audit MVP Design

**Date:** 2026-05-18  
**Status:** Approved  
**Scope:** `bcode audit` command only. Phase 2 (watch) and Phase 3 (hooks) are out of scope.

---

## 1. What We're Building

`bcode audit --task "..." [--commits N] [--typecheck] [--json]`

Post-session scanner. Runs after an AI coding agent finishes. Inspects git state, parses optional Claude Code transcript logs, runs 4 detectors, produces a risk score and terminal report.

Target: under 500 lines of core Python. Zero required runtime deps beyond `click`.

---

## 2. Decisions Made (and Why)

| Decision | Choice | Reason |
|---|---|---|
| Validation source in audit mode | Claude Code transcript logs, graceful fallback | Shell history is unreliable; transcript is structured and scoped |
| Method-call hallucination detection | Delegate to mypy/pyright subprocess, opt-in via `--typecheck` | Reimplementing a type checker is out of scope; subprocess keeps it fast by default |
| Output format | Terminal by default, `--json` flag for CI | JSON adds no complexity (dataclasses.asdict), enables CI integration |
| Architecture | Package with Detector protocol | Testable from day one; plugin API in Phase 4 is natural evolution |
| Scope drift severity | WARN only, never FAIL/critical | Noisiest detector; informational labeling preserves trust |

---

## 3. Project Structure

```
bcode/
  __init__.py
  cli.py           # click entrypoint
  audit.py         # orchestrator: runs detectors, builds AuditResult
  context.py       # AuditContext, BcodeConfig, is_protected()
  report.py        # terminal + JSON rendering
  git.py           # git diff parser, git log helper → DiffResult
  transcript.py    # Claude Code transcript reader → TranscriptResult
  detectors/
    __init__.py
    base.py        # Finding, Severity, Detector protocol
    imports.py     # hallucination: import resolution (Python + JS/TS)
    validation.py  # enforcement: runners + typecheck subprocess (opt-in)
    scope.py       # drift: task tokens vs changed file paths
    breakfix.py    # loops: commit_count per file across session window

pyproject.toml
tests/
  fixtures/
    diffs/         # raw .diff files for parser + detector tests
    transcripts/   # .json files matching TranscriptResult schema
    manifests/     # requirements.txt, package.json for import resolution
  test_git.py
  test_transcript.py
  test_imports.py
  test_validation.py
  test_scope.py
  test_breakfix.py
  test_audit.py
  test_report.py
```

---

## 4. Data Contracts

### `base.py`

```python
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

class Severity(Enum):
    INFO = "info"   # no score impact
    WARN = "warn"   # -10 pts
    FAIL = "fail"   # -25 pts

@dataclass(frozen=True)
class Finding:
    detector: str          # "imports" | "validation" | "scope" | "breakfix"
    severity: Severity
    message: str           # "import 'jose' not found in site-packages"
    file: Path | None = None
    critical: bool = False # if True, score is capped at 49 (RED) regardless of total

class Detector(Protocol):
    @property
    def name(self) -> str: ...
    def run(self, ctx: "AuditContext") -> list[Finding]: ...
```

### `git.py`

```python
@dataclass
class ChangedFile:
    path: Path
    added_lines: list[str]
    removed_lines: list[str]
    commit_count: int  # commits touching this file in session window; 0 when --commits=0 (unstaged diff)

@dataclass
class DiffResult:
    files: list[ChangedFile]
    repo_root: Path
```

### `transcript.py`

**Real format (verified):** JSONL files at `~/.claude/projects/<cwd-hash>/*.jsonl`. One JSON object per line. Bash commands appear in `type: "assistant"` entries as `message.content[].type == "tool_use"` with `name: "Bash"`. The paired `toolUseResult` has `{stdout, stderr, interrupted}` — **no `exitCode` field**. Exit codes are not stored.

Fixture schema (normalized format for tests):

```json
{
  "found": true,
  "commands": [
    { "command": "pytest tests/", "stdout": "5 passed", "timestamp": 1716000000.0 },
    { "command": "ruff check .", "stdout": "", "timestamp": 1716000010.0 }
  ]
}
```

```python
@dataclass
class CommandRun:
    command: str
    stdout: str             # from toolUseResult.stdout — used for heuristic failure detection
    timestamp: float
    # exit_code intentionally omitted: not recorded in Claude Code transcripts

@dataclass
class TranscriptResult:
    commands: list[CommandRun]
    found: bool             # False = no transcript found, degrade gracefully
```

Parse logic:
1. Glob `~/.claude/projects/<cwd-hash>/*.jsonl` (hash = cwd path with `/` → `-`)
2. Filter entries: `message.role == "assistant"`, content has `type: "tool_use"`, `name: "Bash"`
3. Extract `input.command`, `timestamp`; pair with `toolUseResult.stdout`
4. If no `.jsonl` found: `TranscriptResult(found=False, commands=[])`

**Consequence for validation.py:** Exit code checking from transcripts is impossible. The `FAIL, critical=True` case for "runner failed" only works via `--typecheck` subprocess. Transcript-based validation detects invocation only (did the runner run?), not success.

### `context.py`

```python
@dataclass
class BcodeConfig:
    run_typecheck: bool = False
    breakfix_warn_threshold: int = 3
    breakfix_fail_threshold: int = 5
    scope_drift_threshold: float = 0.40   # 60% for --commits > 1
    protected_files: list[str] = field(default_factory=lambda: [
        ".env", ".env.*", "*.lock", ".github/**", "*.pem", "*.key"
    ])

@dataclass
class AuditContext:
    diff: DiffResult
    task: str
    transcript: TranscriptResult | None = None
    repo_root: Path = field(default_factory=Path)
    config: BcodeConfig = field(default_factory=BcodeConfig)

from fnmatch import fnmatch

def is_protected(path: Path, config: BcodeConfig) -> bool:
    name = path.name
    full = str(path)
    return any(
        fnmatch(name, pattern) or fnmatch(full, pattern)
        for pattern in config.protected_files
    )
```

Config loaded from `.bcode.toml` in repo root if present. No required config.

### `audit.py`

```python
SEVERITY_WEIGHTS = {Severity.FAIL: 25, Severity.WARN: 10, Severity.INFO: 0}

def risk_score(findings: list[Finding]) -> int:
    score = 100
    for f in findings:
        score -= SEVERITY_WEIGHTS[f.severity]
    if any(f.critical for f in findings):
        score = min(score, 49)
    return max(0, score)

def build_recommendation(findings: list[Finding]) -> str:
    criticals = [f for f in findings if f.critical]
    fails = [f for f in findings if f.severity == Severity.FAIL and not f.critical]
    warns = [f for f in findings if f.severity == Severity.WARN]
    if criticals:
        reasons = "; ".join(f.message for f in criticals)
        return f"Do not commit. {reasons}."
    if fails:
        return "Do not commit. Fix failing checks before committing."
    if warns:
        return "Review flagged files before committing."
    return "Session looks clean. Proceed."

@dataclass
class AuditResult:
    task: str
    findings: list[Finding]
    score: int
    files_changed: int
    transcript_found: bool
    relevant_categories: set[str]
    recommendation: str
```

---

## 5. Detector Logic

### `imports.py` — Hallucination: import resolution

**Python:**  
Parse `added_lines` for `import X` / `from X import Y`. Extract module root. Skip if:
- starts with `.` or `__`
- `_is_local_module(root, repo_root)` — checks if `<root>.py` or `<root>/` exists in repo

Resolve via `importlib.util.find_spec(root)`. Fallback: parse `pip list` output. Miss → `Finding(severity=FAIL, critical=True)`.

```python
SKIP_PREFIXES = (".", "__")

def _is_local_module(name: str, repo_root: Path) -> bool:
    base = name.split(".")[0]
    return (repo_root / base).is_dir() or (repo_root / f"{base}.py").exists()
```

**JS/TS:**  
Parse `import ... from 'X'` / `require('X')`. Skip relative imports. Handle scoped packages and subpath imports:

```python
def resolve_js_import(specifier: str, repo_root: Path) -> bool:
    if specifier.startswith("."):
        return True  # relative, skip
    base = specifier.split("/")[0]
    if specifier.startswith("@"):
        parts = specifier.split("/")
        if len(parts) < 2:
            return True
        base = f"{parts[0]}/{parts[1]}"
    return (repo_root / "node_modules" / base).exists()
```

### `validation.py` — Enforcement: did runners run?

Known runners:
```python
RUNNERS = {
    "test":      ["pytest", "jest", "vitest", "go test", "cargo test"],
    "lint":      ["ruff", "eslint", "golangci-lint", "rubocop"],
    "typecheck": ["mypy", "pyright", "tsc"],
    "build":     ["npm run build", "cargo build", "go build"],
}
```

Infer relevant categories from diff file extensions before checking:
```python
def infer_relevant_categories(diff: DiffResult) -> set[str]:
    categories = set()
    for f in diff.files:
        ext = f.path.suffix
        if ext in (".py",):
            categories.update(["test", "lint", "typecheck"])
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            categories.update(["test", "lint", "typecheck", "build"])
        if ext in (".go",):
            categories.update(["test", "build"])
    return categories
```

Match commands using argv prefix, not substring:
```python
def command_matches_runner(command: str, runner: str) -> bool:
    argv = command.strip().split()
    if not argv:
        return False
    runner_tokens = runner.split()
    return argv[:len(runner_tokens)] == runner_tokens
```

- `transcript.found=False` → single `INFO` finding, no penalization
- Runner in relevant categories, not in transcript → `FAIL`
- Runner ran but `stdout` contains failure indicators (`"FAILED"`, `"error:"`, `"AssertionError"`) → `WARN` "pytest ran — stdout suggests failures (verify manually)". Heuristic only, not `critical`.
- `--typecheck` flag: run `mypy`/`pyright` as subprocess on changed files only. If not installed → `INFO`. Failures → `FAIL, critical=True`.
- `--typecheck` not set, typecheck runner absent → `INFO` "run with --typecheck to verify"
- **Note:** exit codes are not available from Claude Code transcripts. Success detection from transcripts is heuristic (stdout) only. Definitive failure detection requires `--typecheck` subprocess.

### `scope.py` — Drift: task tokens vs file paths

```python
STOPWORDS = frozenset({
    "fix", "add", "the", "a", "an", "in", "on", "for", "to",
    "and", "or", "with", "update", "change", "make", "get",
    "set", "use", "remove", "delete", "create", "from", "into",
    "bug", "issue", "error", "problem", "broken", "feature",
})
```

Task → tokens (split, lowercase, strip stopwords). File is in-scope if any token appears in its path string. Out-of-scope files: if ratio > `scope_drift_threshold` (0.40 default, 0.60 for `--commits > 1`) → `WARN` per out-of-scope file. Never `FAIL`. Never `critical`.

### `breakfix.py` — Loops: repeated patches

Use `commit_count` from `ChangedFile`:
- `commit_count >= breakfix_fail_threshold (5)` → `FAIL`
- `commit_count >= breakfix_warn_threshold (3)` → `WARN`
- Only meaningful with `--commits N`. If unstaged-only diff → single `INFO` "break-fix detection requires --commits"

---

## 6. CLI

```python
@click.command()
@click.option("--task", "-t", required=True)
@click.option("--commits", "-c", default=0, type=int)
@click.option("--typecheck", is_flag=True, default=False)
@click.option("--repo", default=".", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, default=False)
def audit(task, commits, typecheck, repo, output_json): ...
```

---

## 7. Report Rendering

Terminal output order: header → hallucination → validation → scope → break-fix → score → recommendation.

Unicode fallback:
```python
def _supports_unicode() -> bool:
    return sys.stdout.encoding and sys.stdout.encoding.lower() in ("utf-8", "utf8")

SYMBOLS = {
    "pass":   "✓" if _supports_unicode() else "OK",
    "fail":   "✗" if _supports_unicode() else "XX",
    "warn":   "⚠" if _supports_unicode() else "!",
    "red":    "🔴" if _supports_unicode() else "[RED]",
    "yellow": "🟡" if _supports_unicode() else "[YELLOW]",
    "green":  "🟢" if _supports_unicode() else "[GREEN]",
}
```

JSON: `print(json.dumps(dataclasses.asdict(result), indent=2, default=str))`. `default=str` handles `Path` and `Severity` enum serialization.

Score bands: ≥80 GREEN, 50–79 YELLOW, <50 RED.

---

## 8. Fixture Inventory

```
tests/fixtures/
  diffs/
    clean.diff
    hallucinated_import.diff        # python: 'jose' not installed
    local_module_import.diff        # regression guard — must NOT trigger
    scoped_js_import.diff           # @scope/package resolution
    scope_drift.diff                # 8 files, 1 relevant
    breakfix_3commits.diff          # commit_count=3 → WARN
    breakfix_5commits.diff          # commit_count=5 → FAIL
    protected_file_modified.diff    # .env modified → WARN
  transcripts/
    ran_all.json                    # pytest + ruff + mypy, exit 0
    skipped_tests.json              # ruff only
    false_success.json              # pytest exit 1
    no_transcript.json              # found=false, commands=[]
  manifests/
    requirements.txt                # includes python-jose (not jose)
    package.json                    # includes react, @scope/package
```

---

## 9. Test List

```python
# test_git.py
test_parses_clean_diff()
test_parses_added_lines()
test_commit_count_per_file()

# test_transcript.py
test_parses_ran_all()
test_parses_no_transcript()

# test_imports.py
test_hallucinated_import_detected()
test_local_module_skipped()           # regression guard
test_scoped_js_package_resolved()
test_scoped_js_package_missing()

# test_validation.py
test_all_runners_found()
test_missing_test_runner()
test_failed_exit_code()
test_no_transcript_is_info_only()

# test_scope.py
test_clean_scope()
test_drift_above_threshold()
test_large_refactor_threshold()
test_protected_file_triggers_warn()

# test_breakfix.py
test_below_threshold()
test_warn_threshold()
test_fail_threshold()
test_no_commits_flag_is_info()

# test_audit.py
test_full_session_clean()
test_critical_finding_forces_red()
test_recommendation_multi_critical()
test_audit_completes_without_transcript()

# test_report.py
test_terminal_render_clean_session()
test_terminal_render_critical_finding()
test_json_render_is_valid_json()
test_ascii_fallback()
```

---

## 10. Build Order

```
1.  git.py + transcript.py
2.  tests/fixtures/  (define transcript schema first)
3.  test_git.py + test_transcript.py
4.  context.py
5.  detectors/base.py
6.  detectors/imports.py  →  test_imports.py
7.  detectors/validation.py  →  test_validation.py
8.  detectors/scope.py  →  test_scope.py
9.  detectors/breakfix.py  →  test_breakfix.py
10. audit.py  →  test_audit.py
11. report.py  →  test_report.py
12. cli.py  (smoke test)
```

Never move to the next module with a failing test in the current one.

---

## 11. `pyproject.toml`

```toml
[project]
name = "bcode"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "tomllib; python_version < '3.11'",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[project.scripts]
bcode = "bcode.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--tb=short"

[tool.coverage.run]
source = ["bcode"]
omit = ["tests/*"]

[tool.coverage.report]
show_missing = true
fail_under = 80
```

---

## 12. What's Explicitly Out of Scope (Phase 1)

- `bcode watch` — live file monitoring
- `bcode hooks` — agent hook integration
- JSON output (Phase 1 has `--json` but no CI action)
- Protected file detection as a standalone detector (checked inside `scope.py` using `is_protected()` from `context.py`)
- Language packs beyond Python and JS/TS
- VS Code extension
- GitHub Actions integration
- Any LLM layer
