from pathlib import Path
from bcode.detectors.validation import ValidationDetector, command_matches_runner
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.transcript import TranscriptResult, CommandRun
from bcode.context import AuditContext


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
    ]
    ctx = _py_ctx(commands)
    findings = ValidationDetector().run(ctx)
    assert all(f.severity != Severity.FAIL for f in findings)


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
    assert any("--typecheck" in f.message for f in info_findings)
