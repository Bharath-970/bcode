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
    # 2 out of 4 = 50% → below 60% → no WARN
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
