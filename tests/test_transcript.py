from pathlib import Path
import json as json_module
from bcode.transcript import load_fixture, TranscriptResult

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


# --- Tests for _parse_jsonl and load_transcript ---

def test_parse_jsonl_extracts_bash_commands(tmp_path):
    from bcode.transcript import _parse_jsonl
    lines = [
        json_module.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "Bash",
                        "input": {"command": "pytest tests/"}
                    }
                ]
            }
        }),
        json_module.dumps({
            "timestamp": "2024-01-01T00:00:01Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01",
                        "content": "5 passed"
                    }
                ]
            },
            "toolUseResult": {"stdout": "5 passed"}
        }),
    ]
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text("\n".join(lines))

    commands = _parse_jsonl(jsonl_file)
    assert len(commands) == 1
    assert commands[0].command == "pytest tests/"
    assert commands[0].stdout == "5 passed"
    assert commands[0].timestamp > 0


def test_parse_jsonl_skips_non_bash_tools(tmp_path):
    from bcode.transcript import _parse_jsonl
    lines = [
        json_module.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_02",
                        "name": "Read",
                        "input": {"file_path": "src/main.py"}
                    }
                ]
            }
        }),
    ]
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text("\n".join(lines))

    commands = _parse_jsonl(jsonl_file)
    assert commands == []


def test_parse_jsonl_skips_invalid_json_lines(tmp_path):
    from bcode.transcript import _parse_jsonl
    content = "not valid json\n" + json_module.dumps({
        "timestamp": "2024-01-01T00:00:00Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
            ]
        }
    })
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(content)
    # Should not raise, just skip invalid lines
    commands = _parse_jsonl(jsonl_file)
    assert commands == []  # no tool_result to pair with


def test_parse_jsonl_bad_timestamp_falls_back_to_zero(tmp_path):
    from bcode.transcript import _parse_jsonl
    lines = [
        json_module.dumps({
            "timestamp": "NOT-A-TIMESTAMP",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
                ]
            }
        }),
        json_module.dumps({
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1"}]
            },
            "toolUseResult": {"stdout": "file.py"}
        }),
    ]
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text("\n".join(lines))
    commands = _parse_jsonl(jsonl_file)
    assert len(commands) == 1
    assert commands[0].timestamp == 0.0


def test_load_transcript_not_found(tmp_path):
    from bcode.transcript import load_transcript
    result = load_transcript(tmp_path)
    assert result.found is False
    assert result.commands == []


def test_load_transcript_empty_project_dir(tmp_path):
    from bcode.transcript import load_transcript, _cwd_to_hash
    cwd_hash = _cwd_to_hash(tmp_path)
    project_dir = Path.home() / ".claude" / "projects" / cwd_hash
    project_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = load_transcript(tmp_path)
        assert result.found is False
        assert result.commands == []
    finally:
        project_dir.rmdir()


def test_load_transcript_reads_latest_jsonl(tmp_path):
    from bcode.transcript import load_transcript, _cwd_to_hash
    import time
    cwd_hash = _cwd_to_hash(tmp_path)
    project_dir = Path.home() / ".claude" / "projects" / cwd_hash
    project_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Write two jsonl files; the second (newer) has one Bash command
        older = project_dir / "older.jsonl"
        newer = project_dir / "newer.jsonl"
        older.write_text(json_module.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": []}
        }))
        time.sleep(0.01)  # ensure mtime ordering
        lines = [
            json_module.dumps({
                "timestamp": "2024-01-02T00:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest"}}
                    ]
                }
            }),
            json_module.dumps({
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "t1"}]
                },
                "toolUseResult": {"stdout": "1 passed"}
            }),
        ]
        newer.write_text("\n".join(lines))
        result = load_transcript(tmp_path)
        assert result.found is True
        assert len(result.commands) == 1
        assert result.commands[0].command == "pytest"
    finally:
        for f in project_dir.glob("*.jsonl"):
            f.unlink()
        project_dir.rmdir()
