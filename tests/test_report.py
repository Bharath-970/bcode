from io import StringIO
from pathlib import Path
import json
import sys
from unittest.mock import patch
from bcode.audit import AuditResult
from bcode.detectors.base import Finding, Severity
from bcode.report import render, _supports_unicode


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
    from unittest.mock import Mock
    mock_stdout = Mock()
    mock_stdout.encoding = "ascii"
    with patch("sys.stdout", mock_stdout):
        assert _supports_unicode() is False
