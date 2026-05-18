# bcode Phase 1 Audit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `bcode audit --task "..." [--commits N] [--typecheck] [--json]` — a post-session AI agent reliability scanner that detects hallucinated imports, missing validation, scope drift, and break-fix loops.

**Architecture:** Python package with a `Detector` protocol; each detector receives an `AuditContext` dataclass and returns `list[Finding]`. `audit.py` orchestrates, `report.py` renders. No LLM. No external runtime deps beyond `click`.

**Tech Stack:** Python 3.10+, click 8+, hatchling (build), pytest + pytest-cov (dev), importlib (stdlib), subprocess (stdlib), fnmatch (stdlib), tomllib (stdlib 3.11+ / backport 3.10).

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `bcode/__init__.py` | Public API exports |
| `bcode/git.py` | `parse_unstaged()`, `parse_commits()` → `DiffResult` |
| `bcode/transcript.py` | `load_transcript()`, `load_fixture()` → `TranscriptResult` |
| `bcode/context.py` | `AuditContext`, `BcodeConfig`, `is_protected()`, `load_config()` |
| `bcode/detectors/base.py` | `Severity`, `Finding`, `Detector` protocol |
| `bcode/detectors/imports.py` | Python + JS/TS import resolution |
| `bcode/detectors/validation.py` | Runner invocation detection + typecheck subprocess |
| `bcode/detectors/scope.py` | Task token vs file path matching + protected file check |
| `bcode/detectors/breakfix.py` | `commit_count` threshold detection |
| `bcode/audit.py` | `run()`, `risk_score()`, `build_recommendation()`, `AuditResult` |
| `bcode/report.py` | Terminal + JSON rendering, unicode fallback |
| `bcode/cli.py` | `click` entrypoint, `main()` |
| `tests/fixtures/diffs/*.diff` | Raw unified diffs for `test_git.py` |
| `tests/fixtures/transcripts/*.json` | Fixture schema for `test_transcript.py` |
| `tests/fixtures/manifests/*` | Package manifests for `test_imports.py` |
| `tests/test_git.py` | Parser correctness |
| `tests/test_transcript.py` | Parser correctness |
| `tests/test_imports.py` | Import resolution logic |
| `tests/test_validation.py` | Runner detection logic |
| `tests/test_scope.py` | Drift detection + protected files |
| `tests/test_breakfix.py` | Loop detection |
| `tests/test_audit.py` | Integration: orchestrator + scoring |
| `tests/test_report.py` | Rendering: terminal + JSON |

---

## Task 1: Scaffold — Project Structure + pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `bcode/__init__.py`, `bcode/git.py`, `bcode/transcript.py`, `bcode/context.py`, `bcode/report.py`, `bcode/audit.py`, `bcode/cli.py`
- Create: `bcode/detectors/__init__.py`, `bcode/detectors/base.py`, `bcode/detectors/imports.py`, `bcode/detectors/validation.py`, `bcode/detectors/scope.py`, `bcode/detectors/breakfix.py`
- Create: `tests/__init__.py`, `tests/fixtures/diffs/`, `tests/fixtures/transcripts/`, `tests/fixtures/manifests/`

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/bharath/Documents/project
mkdir -p bcode/detectors tests/fixtures/diffs tests/fixtures/transcripts tests/fixtures/manifests
touch bcode/__init__.py bcode/git.py bcode/transcript.py bcode/context.py bcode/report.py bcode/audit.py bcode/cli.py
touch bcode/detectors/__init__.py bcode/detectors/base.py bcode/detectors/imports.py bcode/detectors/validation.py bcode/detectors/scope.py bcode/detectors/breakfix.py
touch tests/__init__.py tests/test_git.py tests/test_transcript.py tests/test_imports.py tests/test_validation.py tests/test_scope.py tests/test_breakfix.py tests/test_audit.py tests/test_report.py
```

- [ ] **Step 2: Write pyproject.toml**

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

- [ ] **Step 3: Create venv and install**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: `Successfully installed bcode-0.1.0`

- [ ] **Step 4: Verify pytest can run**

```bash
pytest --collect-only
```

Expected: `0 tests collected` (no errors).

- [ ] **Step 5: Initialize git and commit**

```bash
git init
echo ".venv/\n__pycache__/\n*.egg-info/\n.coverage\n" > .gitignore
git add pyproject.toml .gitignore bcode/ tests/
git commit -m "feat: scaffold bcode package structure"
```

---

## Task 2: Fixtures — Write All Input Data Files

**Files:**
- Create: `tests/fixtures/diffs/clean.diff`
- Create: `tests/fixtures/diffs/hallucinated_import.diff`
- Create: `tests/fixtures/diffs/local_module_import.diff`
- Create: `tests/fixtures/diffs/multi_file.diff`
- Create: `tests/fixtures/transcripts/ran_all.json`
- Create: `tests/fixtures/transcripts/skipped_tests.json`
- Create: `tests/fixtures/transcripts/false_success.json`
- Create: `tests/fixtures/transcripts/no_transcript.json`
- Create: `tests/fixtures/manifests/requirements.txt`
- Create: `tests/fixtures/manifests/package.json`

- [ ] **Step 1: Write clean.diff** (single file, no suspicious imports)

```diff
diff --git a/src/auth.py b/src/auth.py
index abc1234..def5678 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,4 @@
 def login(user):
+    user.last_login = datetime.now()
     return user
```

Save to `tests/fixtures/diffs/clean.diff`.

- [ ] **Step 2: Write hallucinated_import.diff** (adds `jose` — not installed; python-jose is)

```diff
diff --git a/src/auth/session.py b/src/auth/session.py
index abc1234..def5678 100644
--- a/src/auth/session.py
+++ b/src/auth/session.py
@@ -1,3 +1,5 @@
+import jose
+from jose import jwt
 import os
 import sys
```

Save to `tests/fixtures/diffs/hallucinated_import.diff`.

- [ ] **Step 3: Write local_module_import.diff** (local module — must NOT trigger false positive)

```diff
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,2 +1,3 @@
+from src.auth.utils import validate_token
 import os
```

Save to `tests/fixtures/diffs/local_module_import.diff`.

- [ ] **Step 4: Write multi_file.diff** (two files, used to test multi-file parsing)

```diff
diff --git a/src/auth.py b/src/auth.py
index abc1234..def5678 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,2 +1,3 @@
+import hashlib
 import os
diff --git a/src/utils.py b/src/utils.py
index abc1234..def5678 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,2 +1,3 @@
+import re
 import sys
```

Save to `tests/fixtures/diffs/multi_file.diff`.

- [ ] **Step 5: Write transcript fixtures**

`tests/fixtures/transcripts/ran_all.json`:
```json
{
  "found": true,
  "commands": [
    {"command": "pytest tests/", "stdout": "5 passed in 0.8s", "timestamp": 1716000000.0},
    {"command": "ruff check .", "stdout": "", "timestamp": 1716000010.0},
    {"command": "mypy src/", "stdout": "Success: no issues found", "timestamp": 1716000020.0}
  ]
}
```

`tests/fixtures/transcripts/skipped_tests.json`:
```json
{
  "found": true,
  "commands": [
    {"command": "ruff check .", "stdout": "", "timestamp": 1716000010.0}
  ]
}
```

`tests/fixtures/transcripts/false_success.json`:
```json
{
  "found": true,
  "commands": [
    {"command": "pytest tests/", "stdout": "FAILED tests/test_auth.py::test_login - AssertionError", "timestamp": 1716000000.0}
  ]
}
```

`tests/fixtures/transcripts/no_transcript.json`:
```json
{
  "found": false,
  "commands": []
}
```

- [ ] **Step 6: Write package manifests**

`tests/fixtures/manifests/requirements.txt`:
```
click==8.1.7
python-jose==3.3.0
requests==2.31.0
```

`tests/fixtures/manifests/package.json`:
```json
{
  "dependencies": {
    "react": "^18.0.0",
    "@radix-ui/react-button": "^1.0.0",
    "clsx": "^2.0.0"
  }
}
```

- [ ] **Step 7: Commit fixtures**

```bash
git add tests/fixtures/
git commit -m "test: add input fixtures for parser and detector tests"
```

---

## Task 3: git.py — Diff Parser

**Files:**
- Modify: `bcode/git.py`
- Modify: `tests/test_git.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_git.py
from pathlib import Path
import pytest
from bcode.git import _parse_diff_text, DiffResult, ChangedFile

FIXTURES = Path(__file__).parent / "fixtures" / "diffs"

def test_parses_clean_diff():
    text = (FIXTURES / "clean.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 1
    assert result.files[0].path == Path("src/auth.py")
    assert any("user.last_login" in line for line in result.files[0].added_lines)

def test_parses_added_lines_only():
    text = (FIXTURES / "hallucinated_import.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 1
    added = result.files[0].added_lines
    assert "import jose" in added
    assert "from jose import jwt" in added

def test_parses_multi_file():
    text = (FIXTURES / "multi_file.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert len(result.files) == 2
    paths = {f.path for f in result.files}
    assert Path("src/auth.py") in paths
    assert Path("src/utils.py") in paths

def test_commit_count_applied():
    text = (FIXTURES / "multi_file.diff").read_text()
    counts = {"src/auth.py": 4, "src/utils.py": 1}
    result = _parse_diff_text(text, Path("."), commit_counts=counts)
    auth_file = next(f for f in result.files if f.path == Path("src/auth.py"))
    assert auth_file.commit_count == 4

def test_commit_count_zero_when_no_counts():
    text = (FIXTURES / "clean.diff").read_text()
    result = _parse_diff_text(text, Path("."), commit_counts=None)
    assert result.files[0].commit_count == 0
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_git.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` on `bcode.git`.

- [ ] **Step 3: Implement git.py**

```python
# bcode/git.py
from __future__ import annotations
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChangedFile:
    path: Path
    added_lines: list[str]
    removed_lines: list[str]
    commit_count: int  # commits touching this file in session window; 0 when --commits=0


@dataclass
class DiffResult:
    files: list[ChangedFile]
    repo_root: Path


def _parse_diff_text(
    text: str,
    repo_root: Path,
    commit_counts: dict[str, int] | None,
) -> DiffResult:
    files: list[ChangedFile] = []
    current_path: str | None = None
    added: list[str] = []
    removed: list[str] = []

    def _flush() -> None:
        if current_path is not None:
            count = (commit_counts or {}).get(current_path, 0)
            files.append(ChangedFile(
                path=Path(current_path),
                added_lines=added[:],
                removed_lines=removed[:],
                commit_count=count,
            ))

    for line in text.splitlines():
        if line.startswith("diff --git "):
            _flush()
            m = re.match(r"diff --git a/(.*) b/(.*)", line)
            current_path = m.group(2) if m else None
            added, removed = [], []
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    _flush()
    return DiffResult(files=files, repo_root=repo_root)


def parse_unstaged(repo_root: Path) -> DiffResult:
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True, text=True, cwd=repo_root, check=False,
    )
    return _parse_diff_text(result.stdout, repo_root, commit_counts=None)


def parse_commits(repo_root: Path, n: int) -> DiffResult:
    diff_out = subprocess.run(
        ["git", "diff", f"HEAD~{n}", "HEAD"],
        capture_output=True, text=True, cwd=repo_root, check=False,
    ).stdout

    log_out = subprocess.run(
        ["git", "log", "--name-only", "--pretty=format:", f"HEAD~{n}..HEAD"],
        capture_output=True, text=True, cwd=repo_root, check=False,
    ).stdout

    counts: dict[str, int] = {}
    for line in log_out.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1

    return _parse_diff_text(diff_out, repo_root, commit_counts=counts)
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_git.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/git.py tests/test_git.py
git commit -m "feat: implement git diff parser with commit_count support"
```

---

## Task 4: transcript.py — Transcript Parser

**Files:**
- Modify: `bcode/transcript.py`
- Modify: `tests/test_transcript.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transcript.py
from pathlib import Path
import pytest
from bcode.transcript import load_fixture, TranscriptResult, CommandRun

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"

def test_parses_ran_all():
    result = load_fixture(FIXTURES / "ran_all.json")
    assert result.found is True
    assert len(result.commands) == 3
    cmds = [c.command for c in result.commands]
    assert "pytest tests/" in cmds
    assert "ruff check ." in cmds
    assert "mypy src/" in cmds

def test_parses_skipped_tests():
    result = load_fixture(FIXTURES / "skipped_tests.json")
    assert result.found is True
    assert len(result.commands) == 1
    assert result.commands[0].command == "ruff check ."

def test_parses_false_success_stdout():
    result = load_fixture(FIXTURES / "false_success.json")
    assert result.found is True
    assert "FAILED" in result.commands[0].stdout

def test_parses_no_transcript():
    result = load_fixture(FIXTURES / "no_transcript.json")
    assert result.found is False
    assert result.commands == []

def test_stdout_preserved():
    result = load_fixture(FIXTURES / "ran_all.json")
    pytest_cmd = next(c for c in result.commands if "pytest" in c.command)
    assert "5 passed" in pytest_cmd.stdout
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_transcript.py -v
```

Expected: `ImportError` on `bcode.transcript`.

- [ ] **Step 3: Implement transcript.py**

```python
# bcode/transcript.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CommandRun:
    command: str
    stdout: str
    timestamp: float
    # exit_code intentionally omitted: not recorded in Claude Code transcripts


@dataclass
class TranscriptResult:
    commands: list[CommandRun]
    found: bool


def load_fixture(path: Path) -> TranscriptResult:
    """Load TranscriptResult from fixture JSON schema (for testing)."""
    data = json.loads(path.read_text())
    if not data.get("found", True):
        return TranscriptResult(commands=[], found=False)
    commands = [
        CommandRun(
            command=c["command"],
            stdout=c.get("stdout", ""),
            timestamp=c.get("timestamp", 0.0),
        )
        for c in data.get("commands", [])
    ]
    return TranscriptResult(commands=commands, found=True)


def _cwd_to_hash(cwd: Path) -> str:
    return str(cwd.resolve()).replace("/", "-")


def _parse_timestamp(ts: str) -> float:
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


def _parse_jsonl(path: Path) -> list[CommandRun]:
    commands: list[CommandRun] = []
    pending: dict[str, tuple[str, float]] = {}  # tool_use_id → (command, timestamp)

    for raw_line in path.read_text().splitlines():
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        msg = obj.get("message", {})

        # Collect tool_use entries from assistant messages
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "tool_use" and item.get("name") == "Bash":
                    pending[item["id"]] = (
                        item.get("input", {}).get("command", ""),
                        _parse_timestamp(obj.get("timestamp", "")),
                    )

        # Pair tool_result entries with their tool_use via id
        tr = obj.get("toolUseResult")
        if tr and isinstance(tr, dict) and "stdout" in tr:
            for item in msg.get("content", []):
                if item.get("type") == "tool_result":
                    tid = item.get("tool_use_id", "")
                    if tid in pending:
                        command, timestamp = pending.pop(tid)
                        commands.append(CommandRun(
                            command=command,
                            stdout=tr.get("stdout", ""),
                            timestamp=timestamp,
                        ))

    return commands


def load_transcript(repo_root: Path) -> TranscriptResult:
    """Load most recent Claude Code session transcript for repo_root."""
    cwd_hash = _cwd_to_hash(repo_root)
    project_dir = Path.home() / ".claude" / "projects" / cwd_hash

    if not project_dir.exists():
        return TranscriptResult(commands=[], found=False)

    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not jsonl_files:
        return TranscriptResult(commands=[], found=False)

    commands = _parse_jsonl(jsonl_files[-1])
    return TranscriptResult(commands=commands, found=True)
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_transcript.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/transcript.py tests/test_transcript.py
git commit -m "feat: implement Claude Code transcript parser"
```

---

## Task 5: context.py — AuditContext, BcodeConfig, is_protected

**Files:**
- Modify: `bcode/context.py`

No dedicated tests needed — pure dataclasses and a one-function utility. Tested implicitly through detector tests.

- [ ] **Step 1: Implement context.py**

```python
# bcode/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

# tomllib: stdlib in 3.11+; backport installed via pyproject.toml for 3.10
import tomllib

from bcode.git import DiffResult
from bcode.transcript import TranscriptResult


@dataclass
class BcodeConfig:
    run_typecheck: bool = False
    breakfix_warn_threshold: int = 3
    breakfix_fail_threshold: int = 5
    scope_drift_threshold: float = 0.40
    protected_files: list[str] = field(default_factory=lambda: [
        ".env", ".env.*", "*.lock", ".github/**", "*.pem", "*.key",
    ])


@dataclass
class AuditContext:
    diff: DiffResult
    task: str
    transcript: TranscriptResult | None = None
    repo_root: Path = field(default_factory=Path)
    config: BcodeConfig = field(default_factory=BcodeConfig)


def is_protected(path: Path, config: BcodeConfig) -> bool:
    name = path.name
    full = str(path)
    return any(
        fnmatch(name, pattern) or fnmatch(full, pattern)
        for pattern in config.protected_files
    )


def load_config(repo_root: Path) -> BcodeConfig:
    config_path = repo_root / ".bcode.toml"
    if not config_path.exists():
        return BcodeConfig()
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    cfg = data.get("bcode", {})
    return BcodeConfig(
        run_typecheck=cfg.get("run_typecheck", False),
        breakfix_warn_threshold=cfg.get("breakfix_warn_threshold", 3),
        breakfix_fail_threshold=cfg.get("breakfix_fail_threshold", 5),
        scope_drift_threshold=cfg.get("scope_drift_threshold", 0.40),
        protected_files=cfg.get("protected_files", BcodeConfig().protected_files),
    )
```

- [ ] **Step 2: Commit**

```bash
git add bcode/context.py
git commit -m "feat: add AuditContext, BcodeConfig, is_protected"
```

---

## Task 6: detectors/base.py — Finding, Severity, Detector Protocol

**Files:**
- Modify: `bcode/detectors/base.py`

No dedicated tests — protocol and frozen dataclasses. Verified through detector tests.

- [ ] **Step 1: Implement base.py**

```python
# bcode/detectors/base.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from bcode.context import AuditContext


class Severity(Enum):
    INFO = "info"   # no score impact
    WARN = "warn"   # -10 pts
    FAIL = "fail"   # -25 pts


@dataclass(frozen=True)
class Finding:
    detector: str       # "imports" | "validation" | "scope" | "breakfix"
    severity: Severity
    message: str
    file: Path | None = None
    critical: bool = False  # True → score capped at 49 regardless of total


class Detector(Protocol):
    @property
    def name(self) -> str: ...

    def run(self, ctx: "AuditContext") -> list[Finding]: ...
```

- [ ] **Step 2: Commit**

```bash
git add bcode/detectors/base.py
git commit -m "feat: add Finding, Severity, Detector protocol"
```

---

## Task 7: detectors/imports.py + test_imports.py

**Files:**
- Modify: `bcode/detectors/imports.py`
- Modify: `tests/test_imports.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_imports.py
from pathlib import Path
import pytest
from bcode.detectors.imports import ImportsDetector
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.transcript import TranscriptResult
from bcode.context import AuditContext, BcodeConfig

MANIFESTS = Path(__file__).parent / "fixtures" / "manifests"


def _ctx(added_lines: list[str], repo_root: Path) -> AuditContext:
    cf = ChangedFile(
        path=Path("src/auth.py"),
        added_lines=added_lines,
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=repo_root)
    return AuditContext(diff=diff, task="fix login", repo_root=repo_root)


def test_hallucinated_python_import_detected(tmp_path):
    # 'jose' is not installed; python-jose is (different package name)
    ctx = _ctx(["import jose", "from jose import jwt"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert any(f.severity == Severity.FAIL and f.critical and "jose" in f.message
               for f in findings)


def test_stdlib_import_not_flagged(tmp_path):
    ctx = _ctx(["import os", "from pathlib import Path"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_local_module_import_not_flagged(tmp_path):
    # Create local module structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth").mkdir()
    (tmp_path / "src" / "auth" / "utils.py").write_text("")
    ctx = _ctx(["from src.auth.utils import validate_token"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_dunder_import_skipped(tmp_path):
    ctx = _ctx(["from __future__ import annotations"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_relative_import_skipped(tmp_path):
    ctx = _ctx(["from . import helpers", "from .utils import parse"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_scoped_package_resolved(tmp_path):
    pkg_dir = tmp_path / "node_modules" / "@radix-ui" / "react-button"
    pkg_dir.mkdir(parents=True)
    cf = ChangedFile(
        path=Path("app/Button.tsx"),
        added_lines=["import { Button } from '@radix-ui/react-button'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="add button", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_missing_scoped_package_flagged(tmp_path):
    cf = ChangedFile(
        path=Path("app/Button.tsx"),
        added_lines=["import { x } from '@missing/package'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="add button", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert any(f.severity == Severity.FAIL and "@missing/package" in f.message
               for f in findings)


def test_js_subpath_import_resolved(tmp_path):
    # 'clsx/lite' → check node_modules/clsx
    (tmp_path / "node_modules" / "clsx").mkdir(parents=True)
    cf = ChangedFile(
        path=Path("app/util.ts"),
        added_lines=["import { clsx } from 'clsx/lite'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="fix styles", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_relative_import_skipped(tmp_path):
    cf = ChangedFile(
        path=Path("app/util.ts"),
        added_lines=["import { x } from './helpers'", "import y from '../base'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="fix", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_imports.py -v
```

Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Implement imports.py**

```python
# bcode/detectors/imports.py
from __future__ import annotations
import importlib.util
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from bcode.detectors.base import Detector, Finding, Severity

if TYPE_CHECKING:
    from bcode.context import AuditContext

_PY_EXTENSIONS = {".py"}
_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
_SKIP_PREFIXES = (".", "__")

_PY_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import)"
)
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""
)


def _is_local_module(name: str, repo_root: Path) -> bool:
    base = name.split(".")[0]
    return (repo_root / base).is_dir() or (repo_root / f"{base}.py").exists()


def _resolve_python(module: str) -> bool:
    try:
        spec = importlib.util.find_spec(module)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _resolve_js(specifier: str, repo_root: Path) -> bool:
    if specifier.startswith("."):
        return True  # relative — skip
    if specifier.startswith("@"):
        parts = specifier.split("/")
        if len(parts) < 2:
            return True  # malformed — skip
        base = f"{parts[0]}/{parts[1]}"
    else:
        base = specifier.split("/")[0]
    return (repo_root / "node_modules" / base).exists()


def _check_python_lines(
    lines: list[str], file_path: Path, repo_root: Path
) -> list[Finding]:
    findings: list[Finding] = []
    for line in lines:
        m = _PY_IMPORT_RE.match(line)
        if not m:
            continue
        module = m.group(1) or m.group(2)
        if not module:
            continue
        root = module.split(".")[0]
        if root.startswith(_SKIP_PREFIXES):
            continue
        if _is_local_module(root, repo_root):
            continue
        if not _resolve_python(root):
            findings.append(Finding(
                detector="imports",
                severity=Severity.FAIL,
                message=f"import '{module}' not found in environment",
                file=file_path,
                critical=True,
            ))
    return findings


def _check_js_lines(
    lines: list[str], file_path: Path, repo_root: Path
) -> list[Finding]:
    findings: list[Finding] = []
    for line in lines:
        for specifier in _JS_IMPORT_RE.findall(line):
            if _resolve_js(specifier, repo_root):
                continue
            findings.append(Finding(
                detector="imports",
                severity=Severity.FAIL,
                message=f"import '{specifier}' not found in node_modules",
                file=file_path,
                critical=True,
            ))
    return findings


class ImportsDetector:
    name = "imports"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []
        for changed in ctx.diff.files:
            ext = changed.path.suffix
            if ext in _PY_EXTENSIONS:
                findings.extend(
                    _check_python_lines(changed.added_lines, changed.path, ctx.repo_root)
                )
            elif ext in _JS_EXTENSIONS:
                findings.extend(
                    _check_js_lines(changed.added_lines, changed.path, ctx.repo_root)
                )
        return findings
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_imports.py -v
```

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/detectors/imports.py tests/test_imports.py
git commit -m "feat: implement import hallucination detector (Python + JS/TS)"
```

---

## Task 8: detectors/validation.py + test_validation.py

**Files:**
- Modify: `bcode/detectors/validation.py`
- Modify: `tests/test_validation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_validation.py
from pathlib import Path
import pytest
from bcode.detectors.validation import ValidationDetector, command_matches_runner
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.transcript import TranscriptResult, CommandRun
from bcode.context import AuditContext, BcodeConfig


def _py_ctx(commands: list[CommandRun] | None, found: bool = True) -> AuditContext:
    cf = ChangedFile(
        path=Path("src/auth.py"),
        added_lines=["def login(): pass"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=Path("."))
    transcript = TranscriptResult(commands=commands or [], found=found)
    return AuditContext(diff=diff, task="fix login", transcript=transcript)


def test_all_relevant_runners_found():
    commands = [
        CommandRun("pytest tests/", "5 passed", 0.0),
        CommandRun("ruff check .", "", 0.0),
        CommandRun("mypy src/", "Success: no issues found", 0.0),
    ]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    fail_findings = [f for f in findings if f.severity == Severity.FAIL]
    assert fail_findings == []


def test_missing_test_runner_is_fail():
    commands = [CommandRun("ruff check .", "", 0.0)]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    assert any(
        f.severity == Severity.FAIL and "test" in f.message.lower()
        for f in findings
    )


def test_missing_lint_runner_is_fail():
    commands = [CommandRun("pytest tests/", "3 passed", 0.0)]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    assert any(
        f.severity == Severity.FAIL and "lint" in f.message.lower()
        for f in findings
    )


def test_no_transcript_is_info_only():
    ctx = _py_ctx(commands=None, found=False)
    findings = ValidationDetector().run(ctx)
    assert all(f.severity == Severity.INFO for f in findings)
    assert len(findings) == 1


def test_stdout_failure_indicators_produce_warn():
    commands = [
        CommandRun("pytest tests/", "FAILED tests/test_auth.py::test_login", 0.0),
        CommandRun("ruff check .", "", 0.0),
        CommandRun("mypy src/", "Success: no issues found", 0.0),
    ]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    warn_findings = [f for f in findings if f.severity == Severity.WARN]
    assert any("suggest" in f.message.lower() for f in warn_findings)


def test_command_matches_runner_exact():
    assert command_matches_runner("pytest tests/", "pytest") is True


def test_command_matches_runner_multi_word():
    assert command_matches_runner("npm run build", "npm run build") is True


def test_command_matches_runner_no_substring():
    assert command_matches_runner("run_pytest_wrapper.sh", "pytest") is False


def test_typecheck_absent_is_info_when_flag_not_set():
    commands = [
        CommandRun("pytest tests/", "5 passed", 0.0),
        CommandRun("ruff check .", "", 0.0),
    ]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    info_findings = [f for f in findings if f.severity == Severity.INFO]
    assert any("typecheck" in f.message.lower() or "--typecheck" in f.message
               for f in info_findings)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_validation.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement validation.py**

```python
# bcode/detectors/validation.py
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from bcode.detectors.base import Detector, Finding, Severity
from bcode.git import DiffResult

if TYPE_CHECKING:
    from bcode.context import AuditContext

RUNNERS: dict[str, list[str]] = {
    "test":      ["pytest", "jest", "vitest", "go test", "cargo test"],
    "lint":      ["ruff", "eslint", "golangci-lint", "rubocop"],
    "typecheck": ["mypy", "pyright", "tsc"],
    "build":     ["npm run build", "cargo build", "go build"],
}

FAILURE_INDICATORS = {"FAILED", "error:", "AssertionError", "ERROR"}

_EXT_CATEGORIES: dict[str, set[str]] = {
    ".py":  {"test", "lint", "typecheck"},
    ".ts":  {"test", "lint", "typecheck", "build"},
    ".tsx": {"test", "lint", "typecheck", "build"},
    ".js":  {"test", "lint", "typecheck", "build"},
    ".jsx": {"test", "lint", "typecheck", "build"},
    ".go":  {"test", "build"},
}


def infer_relevant_categories(diff: DiffResult) -> set[str]:
    categories: set[str] = set()
    for f in diff.files:
        categories.update(_EXT_CATEGORIES.get(f.path.suffix, set()))
    return categories


def command_matches_runner(command: str, runner: str) -> bool:
    argv = command.strip().split()
    if not argv:
        return False
    runner_tokens = runner.split()
    return argv[: len(runner_tokens)] == runner_tokens


def _stdout_suggests_failure(stdout: str) -> bool:
    return any(indicator in stdout for indicator in FAILURE_INDICATORS)


class ValidationDetector:
    name = "validation"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        if ctx.transcript is None or not ctx.transcript.found:
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="No transcript found — validation status unknown",
            ))
            return findings

        relevant = infer_relevant_categories(ctx.diff)
        commands_run = [c.command for c in ctx.transcript.commands]

        for category in sorted(relevant):
            if category == "typecheck" and not ctx.config.run_typecheck:
                # Check if user ran it manually; if not, suggest --typecheck
                ran = any(
                    command_matches_runner(cmd, runner)
                    for cmd in commands_run
                    for runner in RUNNERS["typecheck"]
                )
                if not ran:
                    findings.append(Finding(
                        detector="validation",
                        severity=Severity.INFO,
                        message="typecheck not in session — run with --typecheck to verify",
                    ))
                continue

            category_runners = RUNNERS.get(category, [])
            matched_commands = [
                c for c in ctx.transcript.commands
                if any(command_matches_runner(c.command, r) for r in category_runners)
            ]

            if not matched_commands:
                findings.append(Finding(
                    detector="validation",
                    severity=Severity.FAIL,
                    message=f"no {category} runner found in session",
                ))
            else:
                for cmd in matched_commands:
                    if _stdout_suggests_failure(cmd.stdout):
                        findings.append(Finding(
                            detector="validation",
                            severity=Severity.WARN,
                            message=f"{cmd.command.split()[0]} ran — stdout suggests failures (verify manually)",
                        ))

        if ctx.config.run_typecheck:
            findings.extend(_run_typecheck_subprocess(ctx))

        return findings


def _run_typecheck_subprocess(ctx: "AuditContext") -> list[Finding]:
    findings: list[Finding] = []
    py_files = [
        str(f.path) for f in ctx.diff.files if f.path.suffix == ".py"
    ]
    ts_files = [
        str(f.path) for f in ctx.diff.files if f.path.suffix in {".ts", ".tsx"}
    ]

    if py_files:
        result = subprocess.run(
            ["mypy", "--no-error-summary", *py_files],
            capture_output=True, text=True, cwd=ctx.repo_root, check=False,
        )
        if result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector="validation",
                severity=Severity.FAIL,
                message=f"mypy found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))
        elif result.returncode == 127:  # command not found
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="mypy not installed — skipping typecheck",
            ))

    if ts_files:
        result = subprocess.run(
            ["tsc", "--noEmit", "--strict", *ts_files],
            capture_output=True, text=True, cwd=ctx.repo_root, check=False,
        )
        if result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector="validation",
                severity=Severity.FAIL,
                message=f"tsc found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))
        elif result.returncode == 127:
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="tsc not installed — skipping typecheck",
            ))

    return findings
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_validation.py -v
```

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/detectors/validation.py tests/test_validation.py
git commit -m "feat: implement validation enforcement detector"
```

---

## Task 9: detectors/scope.py + test_scope.py

**Files:**
- Modify: `bcode/detectors/scope.py`
- Modify: `tests/test_scope.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scope.py
from pathlib import Path
import pytest
from bcode.detectors.scope import ScopeDetector
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.context import AuditContext, BcodeConfig


def _make_ctx(paths: list[str], task: str, commits: int = 0) -> AuditContext:
    files = [
        ChangedFile(path=Path(p), added_lines=[], removed_lines=[], commit_count=commits)
        for p in paths
    ]
    diff = DiffResult(files=files, repo_root=Path("."))
    return AuditContext(diff=diff, task=task)


def test_all_files_in_scope_no_findings():
    ctx = _make_ctx(["src/auth/login.py", "src/auth/session.py"], "fix login bug")
    findings = ScopeDetector().run(ctx)
    assert findings == []


def test_drift_above_threshold_produces_warn():
    # task "fix login" → token "login"
    # 1 in-scope (auth/login.py), 7 out-of-scope → 7/8 = 87.5% > 40%
    paths = [
        "src/auth/login.py",          # in scope
        "templates/base.html",         # out
        "utils/string_helpers.py",     # out
        "config/settings.py",          # out
        "static/css/main.css",         # out
        "docs/api.md",                 # out
        "scripts/deploy.sh",           # out
        "tests/test_utils.py",         # out
    ]
    ctx = _make_ctx(paths, "fix login bug")
    findings = ScopeDetector().run(ctx)
    warn_findings = [f for f in findings if f.severity == Severity.WARN]
    assert len(warn_findings) >= 1


def test_drift_never_fail_or_critical():
    paths = ["templates/base.html", "utils/helpers.py", "config/settings.py"]
    ctx = _make_ctx(paths, "fix login bug")
    findings = ScopeDetector().run(ctx)
    assert not any(f.severity == Severity.FAIL for f in findings)
    assert not any(f.critical for f in findings)


def test_large_refactor_uses_higher_threshold():
    # With commit_count > 0 (implies --commits flag used), threshold = 0.60
    # 5 out of 8 = 62.5% > 60% → WARN
    # Without higher threshold: 62.5% > 40% → WARN (same result here)
    # Test that a 50% drift (below 60%) does NOT warn for large refactor
    paths = [
        "src/auth/login.py",      # in scope
        "src/auth/session.py",    # in scope
        "templates/base.html",    # out
        "utils/helpers.py",       # out
    ]
    ctx = _make_ctx(paths, "fix login", commits=3)  # commit_count > 0
    findings = ScopeDetector().run(ctx)
    # 2/4 = 50% out of scope < 60% threshold → no WARN
    assert not any(f.severity == Severity.WARN for f in findings)


def test_protected_file_triggers_warn():
    ctx = _make_ctx([".env", "src/auth.py"], "fix login")
    findings = ScopeDetector().run(ctx)
    assert any(
        f.severity == Severity.WARN and ".env" in f.message
        for f in findings
    )


def test_stopwords_stripped_from_task():
    # "fix the login bug" → after stopword removal → ["login"]
    # "login" matches "auth/login.py" → in scope
    ctx = _make_ctx(["src/auth/login.py"], "fix the login bug")
    findings = ScopeDetector().run(ctx)
    assert findings == []
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_scope.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement scope.py**

```python
# bcode/detectors/scope.py
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from bcode.context import is_protected
from bcode.detectors.base import Detector, Finding, Severity
from bcode.git import ChangedFile

if TYPE_CHECKING:
    from bcode.context import AuditContext

# TODO: extract protected file check to detectors/safety.py in Phase 2
STOPWORDS = frozenset({
    "fix", "add", "the", "a", "an", "in", "on", "for", "to",
    "and", "or", "with", "update", "change", "make", "get",
    "set", "use", "remove", "delete", "create", "from", "into",
    "bug", "issue", "error", "problem", "broken", "feature",
})


def _tokenize_task(task: str) -> set[str]:
    return {t for t in task.lower().split() if t not in STOPWORDS}


def _is_in_scope(changed: ChangedFile, tokens: set[str]) -> bool:
    path_str = str(changed.path).lower()
    return any(token in path_str for token in tokens)


class ScopeDetector:
    name = "scope"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        # Protected file check
        for changed in ctx.diff.files:
            if is_protected(changed.path, ctx.config):
                findings.append(Finding(
                    detector="scope",
                    severity=Severity.WARN,
                    message=f"protected file modified: {changed.path}",
                    file=changed.path,
                ))

        # Scope drift check
        tokens = _tokenize_task(ctx.task)
        if not tokens:
            return findings  # no tokens → can't assess scope

        out_of_scope = [f for f in ctx.diff.files if not _is_in_scope(f, tokens)]
        total = len(ctx.diff.files)
        if total == 0:
            return findings

        ratio = len(out_of_scope) / total
        # Use higher threshold when commit_count > 0 (implies --commits flag)
        threshold = (
            0.60
            if any(f.commit_count > 0 for f in ctx.diff.files)
            else ctx.config.scope_drift_threshold
        )

        if ratio > threshold:
            for changed in out_of_scope:
                findings.append(Finding(
                    detector="scope",
                    severity=Severity.WARN,
                    message=f"file outside task scope: {changed.path}",
                    file=changed.path,
                ))

        return findings
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_scope.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/detectors/scope.py tests/test_scope.py
git commit -m "feat: implement scope drift detector with protected file check"
```

---

## Task 10: detectors/breakfix.py + test_breakfix.py

**Files:**
- Modify: `bcode/detectors/breakfix.py`
- Modify: `tests/test_breakfix.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_breakfix.py
from pathlib import Path
import pytest
from bcode.detectors.breakfix import BreakfixDetector
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.context import AuditContext


def _make_ctx(commit_counts: list[int]) -> AuditContext:
    files = [
        ChangedFile(
            path=Path(f"src/file{i}.py"),
            added_lines=[],
            removed_lines=[],
            commit_count=c,
        )
        for i, c in enumerate(commit_counts)
    ]
    diff = DiffResult(files=files, repo_root=Path("."))
    return AuditContext(diff=diff, task="fix bug")


def test_below_warn_threshold_no_findings():
    ctx = _make_ctx([2, 1, 1])
    findings = BreakfixDetector().run(ctx)
    assert findings == []


def test_at_warn_threshold_produces_warn():
    ctx = _make_ctx([3])
    findings = BreakfixDetector().run(ctx)
    assert any(f.severity == Severity.WARN for f in findings)


def test_at_fail_threshold_produces_fail():
    ctx = _make_ctx([5])
    findings = BreakfixDetector().run(ctx)
    assert any(f.severity == Severity.FAIL for f in findings)


def test_above_fail_threshold_produces_fail():
    ctx = _make_ctx([7])
    findings = BreakfixDetector().run(ctx)
    assert any(f.severity == Severity.FAIL for f in findings)


def test_breakfix_never_critical():
    ctx = _make_ctx([10])
    findings = BreakfixDetector().run(ctx)
    assert not any(f.critical for f in findings)


def test_no_commits_flag_produces_info():
    # commit_count == 0 for all files → --commits not used → INFO
    ctx = _make_ctx([0, 0, 0])
    findings = BreakfixDetector().run(ctx)
    assert any(f.severity == Severity.INFO for f in findings)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_breakfix.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement breakfix.py**

```python
# bcode/detectors/breakfix.py
from __future__ import annotations
from typing import TYPE_CHECKING

from bcode.detectors.base import Detector, Finding, Severity

if TYPE_CHECKING:
    from bcode.context import AuditContext


class BreakfixDetector:
    name = "breakfix"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        # If no commit counts, --commits flag was not used
        if all(f.commit_count == 0 for f in ctx.diff.files):
            findings.append(Finding(
                detector="breakfix",
                severity=Severity.INFO,
                message="break-fix detection requires --commits flag",
            ))
            return findings

        warn_t = ctx.config.breakfix_warn_threshold
        fail_t = ctx.config.breakfix_fail_threshold

        for changed in ctx.diff.files:
            c = changed.commit_count
            if c >= fail_t:
                findings.append(Finding(
                    detector="breakfix",
                    severity=Severity.FAIL,
                    message=(
                        f"{changed.path} patched {c} times across {c} commits "
                        f"(threshold: {fail_t})"
                    ),
                    file=changed.path,
                ))
            elif c >= warn_t:
                findings.append(Finding(
                    detector="breakfix",
                    severity=Severity.WARN,
                    message=(
                        f"{changed.path} patched {c} times across {c} commits "
                        f"(threshold: {warn_t})"
                    ),
                    file=changed.path,
                ))

        return findings
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_breakfix.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/detectors/breakfix.py tests/test_breakfix.py
git commit -m "feat: implement break-fix loop detector"
```

---

## Task 11: audit.py + test_audit.py

**Files:**
- Modify: `bcode/audit.py`
- Modify: `tests/test_audit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_audit.py
from pathlib import Path
import pytest
from bcode.audit import run, AuditResult, risk_score, build_recommendation
from bcode.detectors.base import Finding, Severity
from bcode.git import DiffResult, ChangedFile
from bcode.transcript import TranscriptResult
from bcode.context import AuditContext


def _clean_ctx() -> AuditContext:
    cf = ChangedFile(
        path=Path("src/auth.py"),
        added_lines=["import os"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=Path("."))
    transcript = TranscriptResult(commands=[], found=False)
    return AuditContext(diff=diff, task="fix login", transcript=transcript)


def test_full_session_clean_score_near_100():
    result = run(_clean_ctx())
    assert isinstance(result, AuditResult)
    assert result.score >= 80  # INFO findings don't deduct points → high score


def test_critical_finding_forces_score_red():
    findings = [
        Finding(detector="imports", severity=Severity.FAIL,
                message="import 'jose' not found", critical=True),
    ]
    assert risk_score(findings) <= 49


def test_multiple_fails_accumulate():
    findings = [
        Finding(detector="imports", severity=Severity.FAIL, message="a"),
        Finding(detector="validation", severity=Severity.FAIL, message="b"),
        Finding(detector="validation", severity=Severity.FAIL, message="c"),
    ]
    assert risk_score(findings) == 100 - 25 - 25 - 25


def test_warn_deducts_ten():
    findings = [Finding(detector="scope", severity=Severity.WARN, message="x")]
    assert risk_score(findings) == 90


def test_info_no_deduction():
    findings = [Finding(detector="breakfix", severity=Severity.INFO, message="y")]
    assert risk_score(findings) == 100


def test_score_floor_zero():
    findings = [
        Finding(detector="imports", severity=Severity.FAIL, message=str(i), critical=True)
        for i in range(10)
    ]
    assert risk_score(findings) == 0


def test_recommendation_multi_critical():
    findings = [
        Finding(detector="imports", severity=Severity.FAIL,
                message="import 'jose' not found", critical=True),
        Finding(detector="validation", severity=Severity.FAIL,
                message="pytest failed", critical=True),
    ]
    rec = build_recommendation(findings)
    assert "jose" in rec
    assert "pytest" in rec
    assert rec.startswith("Do not commit.")


def test_recommendation_non_critical_fail():
    findings = [Finding(detector="validation", severity=Severity.FAIL, message="x")]
    assert "Do not commit" in build_recommendation(findings)


def test_recommendation_warn_only():
    findings = [Finding(detector="scope", severity=Severity.WARN, message="x")]
    assert "Review" in build_recommendation(findings)


def test_recommendation_clean():
    assert "clean" in build_recommendation([]).lower()


def test_audit_completes_without_transcript():
    ctx = _clean_ctx()
    ctx.transcript.found = False
    result = run(ctx)
    assert result.transcript_found is False
    assert result.score >= 0  # must not crash


def test_audit_result_has_all_fields():
    result = run(_clean_ctx())
    assert hasattr(result, "task")
    assert hasattr(result, "findings")
    assert hasattr(result, "score")
    assert hasattr(result, "files_changed")
    assert hasattr(result, "transcript_found")
    assert hasattr(result, "relevant_categories")
    assert hasattr(result, "recommendation")
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_audit.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement audit.py**

```python
# bcode/audit.py
from __future__ import annotations
from dataclasses import dataclass

from bcode.context import AuditContext
from bcode.detectors.base import Finding, Severity
from bcode.detectors.breakfix import BreakfixDetector
from bcode.detectors.imports import ImportsDetector
from bcode.detectors.scope import ScopeDetector
from bcode.detectors.validation import ValidationDetector, infer_relevant_categories

_DETECTORS = [ImportsDetector(), ValidationDetector(), ScopeDetector(), BreakfixDetector()]

_WEIGHTS = {Severity.FAIL: 25, Severity.WARN: 10, Severity.INFO: 0}


def risk_score(findings: list[Finding]) -> int:
    score = 100
    for f in findings:
        score -= _WEIGHTS[f.severity]
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


def run(ctx: AuditContext) -> AuditResult:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector.run(ctx))

    score = risk_score(findings)
    return AuditResult(
        task=ctx.task,
        findings=findings,
        score=score,
        files_changed=len(ctx.diff.files),
        transcript_found=ctx.transcript.found if ctx.transcript else False,
        relevant_categories=infer_relevant_categories(ctx.diff),
        recommendation=build_recommendation(findings),
    )
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_audit.py -v
```

Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/audit.py tests/test_audit.py
git commit -m "feat: implement audit orchestrator with risk scoring"
```

---

## Task 12: report.py + test_report.py

**Files:**
- Modify: `bcode/report.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report.py
from io import StringIO
from pathlib import Path
import json
import sys
import pytest
from unittest.mock import patch
from bcode.audit import AuditResult
from bcode.detectors.base import Finding, Severity
from bcode.report import render, _supports_unicode, SYMBOLS


def _clean_result() -> AuditResult:
    return AuditResult(
        task="fix login bug",
        findings=[],
        score=100,
        files_changed=2,
        transcript_found=True,
        relevant_categories={"test", "lint"},
        recommendation="Session looks clean. Proceed.",
    )


def _critical_result() -> AuditResult:
    return AuditResult(
        task="fix login bug",
        findings=[
            Finding(detector="imports", severity=Severity.FAIL,
                    message="import 'jose' not found", file=Path("src/auth.py"),
                    critical=True),
        ],
        score=35,
        files_changed=1,
        transcript_found=True,
        relevant_categories={"test", "lint"},
        recommendation="Do not commit. import 'jose' not found.",
    )


def test_terminal_render_clean_session(capsys):
    render(_clean_result(), output_json=False)
    out = capsys.readouterr().out
    assert "fix login bug" in out
    assert "100" in out
    assert "clean" in out.lower() or "green" in out.lower() or "GREEN" in out


def test_terminal_render_critical_shows_recommendation(capsys):
    render(_critical_result(), output_json=False)
    out = capsys.readouterr().out
    assert "Do not commit" in out
    assert "35" in out


def test_json_render_is_valid_json(capsys):
    render(_clean_result(), output_json=True)
    out = capsys.readouterr().out
    data = json.loads(out)  # must not raise
    assert data["score"] == 100
    assert data["task"] == "fix login bug"
    assert "findings" in data
    assert "recommendation" in data


def test_json_render_handles_path_serialization(capsys):
    render(_critical_result(), output_json=True)
    out = capsys.readouterr().out
    data = json.loads(out)  # Path("src/auth.py") must serialize to string
    assert data["findings"][0]["file"] == "src/auth.py"


def test_ascii_fallback_symbols():
    with patch.object(sys.stdout, "encoding", "ascii"):
        # Force re-evaluation — _supports_unicode() is called at render time
        assert _supports_unicode() is False
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_report.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement report.py**

```python
# bcode/report.py
from __future__ import annotations
import dataclasses
import json
import sys
from bcode.audit import AuditResult
from bcode.detectors.base import Severity


def _supports_unicode() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return enc.lower() in ("utf-8", "utf8")


def _get_symbols() -> dict[str, str]:
    if _supports_unicode():
        return {
            "pass": "✓", "fail": "✗", "warn": "⚠",
            "red": "🔴", "yellow": "🟡", "green": "🟢",
        }
    return {
        "pass": "OK", "fail": "XX", "warn": "!",
        "red": "[RED]", "yellow": "[YELLOW]", "green": "[GREEN]",
    }


def _score_band(score: int, sym: dict[str, str]) -> str:
    if score >= 80:
        return f"{sym['green']} LOW RISK"
    if score >= 50:
        return f"{sym['yellow']} REVIEW RECOMMENDED"
    return f"{sym['red']} HIGH RISK"


def _render_terminal(result: AuditResult) -> None:
    sym = _get_symbols()
    sep = "─" * 45

    print("bcode audit — session report")
    print(sep)
    print(f"Task          : {result.task}")
    print(f"Files changed : {result.files_changed}")
    status = "found" if result.transcript_found else "not found (validation partial)"
    print(f"Transcript    : {status}")
    print()

    # Group findings by detector
    by_detector: dict[str, list] = {}
    for f in result.findings:
        by_detector.setdefault(f.detector, []).append(f)

    _render_section("HALLUCINATION DETECTION", by_detector.get("imports", []), sym)
    _render_section("VALIDATION ENFORCEMENT", by_detector.get("validation", []), sym)
    _render_section("SCOPE ANALYSIS [informational]", by_detector.get("scope", []), sym)
    _render_section("BREAK-FIX LOOPS", by_detector.get("breakfix", []), sym)

    print(sep)
    band = _score_band(result.score, sym)
    print(f"Reliability Score : {result.score} / 100   {band}")
    print(f"Recommendation    : {result.recommendation}")
    print(sep)


def _render_section(title: str, findings: list, sym: dict[str, str]) -> None:
    print(title)
    if not findings:
        print(f"  {sym['pass']} No issues detected")
    for f in findings:
        icon = sym["fail"] if f.severity == Severity.FAIL else (
            sym["warn"] if f.severity == Severity.WARN else "~"
        )
        loc = f" — {f.file}" if f.file else ""
        print(f"  {icon} {f.message}{loc}")
    print()


def _render_json(result: AuditResult) -> None:
    print(json.dumps(dataclasses.asdict(result), indent=2, default=str))


def render(result: AuditResult, output_json: bool = False) -> None:
    if output_json:
        _render_json(result)
    else:
        _render_terminal(result)
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_report.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add bcode/report.py tests/test_report.py
git commit -m "feat: implement terminal and JSON report rendering"
```

---

## Task 13: cli.py — Click Entrypoint

**Files:**
- Modify: `bcode/cli.py`

- [ ] **Step 1: Implement cli.py**

```python
# bcode/cli.py
from __future__ import annotations
import sys
from pathlib import Path

import click

from bcode import audit as audit_module
from bcode.context import AuditContext, load_config
from bcode.git import parse_commits, parse_unstaged
from bcode.report import render
from bcode.transcript import load_transcript


@click.command()
@click.option("--task", "-t", required=True, help="Declared task description")
@click.option("--commits", "-c", default=0, type=int,
              help="Audit last N commits (0 = unstaged diff)")
@click.option("--typecheck", is_flag=True, default=False,
              help="Run mypy/pyright/tsc as subprocess on changed files")
@click.option("--repo", default=".", type=click.Path(exists=True),
              help="Repo root (default: cwd)")
@click.option("--json", "output_json", is_flag=True, default=False,
              help="Emit JSON instead of terminal output")
def audit(task: str, commits: int, typecheck: bool, repo: str, output_json: bool) -> None:
    repo_root = Path(repo).resolve()
    config = load_config(repo_root)
    config.run_typecheck = typecheck

    diff = parse_commits(repo_root, commits) if commits > 0 else parse_unstaged(repo_root)
    transcript = load_transcript(repo_root)

    ctx = AuditContext(
        diff=diff,
        task=task,
        transcript=transcript,
        repo_root=repo_root,
        config=config,
    )

    result = audit_module.run(ctx)
    render(result, output_json=output_json)

    if result.score < 50:
        sys.exit(1)


def main() -> None:
    audit()
```

- [ ] **Step 2: Smoke test**

```bash
cd /tmp && git init smoke-test && cd smoke-test
echo "import requests" > main.py
git add main.py && git commit -m "init"
bcode audit --task "add main module" --repo .
```

Expected: terminal report with no crash. Score may vary based on environment.

- [ ] **Step 3: Test exit codes**

```bash
# Clean repo → exit 0
bcode audit --task "add main" --repo /tmp/smoke-test
echo "Exit: $?"

# Check JSON output parses
bcode audit --task "add main" --repo /tmp/smoke-test --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('score:', d['score'])"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/bharath/Documents/project
git add bcode/cli.py
git commit -m "feat: implement CLI entrypoint with exit code for CI"
```

---

## Task 14: bcode/__init__.py — Public API

**Files:**
- Modify: `bcode/__init__.py`

- [ ] **Step 1: Implement __init__.py**

```python
# bcode/__init__.py
from bcode.audit import AuditResult, run as audit_run
from bcode.context import AuditContext, BcodeConfig
from bcode.detectors.base import Finding, Severity

__all__ = [
    "AuditResult",
    "AuditContext",
    "BcodeConfig",
    "Finding",
    "Severity",
    "audit_run",
]
__version__ = "0.1.0"
```

- [ ] **Step 2: Verify import works**

```bash
python3 -c "import bcode; print(bcode.__version__); print(bcode.Severity.FAIL)"
```

Expected: `0.1.0` then `Severity.FAIL`.

- [ ] **Step 3: Run full test suite**

```bash
pytest --tb=short -v
```

Expected: all tests pass.

- [ ] **Step 4: Check coverage**

```bash
pytest --cov=bcode --cov-report=term-missing
```

Expected: `≥ 80%` coverage (enforced by `fail_under = 80` in pyproject.toml).

- [ ] **Step 5: Final commit**

```bash
git add bcode/__init__.py
git commit -m "feat: expose public API in bcode.__init__"
```

---

## Self-Review Checklist

After all tasks complete:

- [ ] `pytest` passes with 0 failures
- [ ] `pytest --cov=bcode` reports ≥ 80% coverage
- [ ] `bcode audit --task "test" --repo .` runs without error
- [ ] `bcode audit --task "test" --repo . --json | python3 -m json.tool` parses cleanly
- [ ] `bcode audit --task "test" --repo . --typecheck` runs without error (mypy installed or graceful INFO)
- [ ] No `TBD`, `TODO`, or placeholder code in `bcode/` (outside the one `# TODO: extract` comment in scope.py)
