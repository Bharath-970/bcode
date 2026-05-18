from pathlib import Path
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
