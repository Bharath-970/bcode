from pathlib import Path
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
