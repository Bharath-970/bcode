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
