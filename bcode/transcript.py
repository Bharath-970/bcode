from __future__ import annotations
import json
from dataclasses import dataclass
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
    """Convert cwd path to Claude Code project hash (/ → -)."""
    return str(cwd.resolve()).replace("/", "-")


def _parse_timestamp(ts: str) -> float:
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


def _parse_jsonl(path: Path) -> list[CommandRun]:
    """Parse Claude Code JSONL transcript. Pairs tool_use with toolUseResult via tool_use_id."""
    commands: list[CommandRun] = []
    # Maps tool_use_id → (command, timestamp) from assistant messages
    pending: dict[str, tuple[str, float]] = {}

    for raw_line in path.read_text().splitlines():
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        msg = obj.get("message", {})

        # Collect Bash tool_use entries from assistant messages
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if item.get("type") == "tool_use" and item.get("name") == "Bash":
                    pending[item["id"]] = (
                        item.get("input", {}).get("command", ""),
                        _parse_timestamp(obj.get("timestamp", "")),
                    )

        # Pair tool_result entries with their pending tool_use via id
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
    """Load most recent Claude Code session transcript for repo_root.

    Looks for JSONL files at ~/.claude/projects/<cwd-hash>/*.jsonl.
    Returns TranscriptResult(found=False) if no transcript exists.
    """
    cwd_hash = _cwd_to_hash(repo_root)
    project_dir = Path.home() / ".claude" / "projects" / cwd_hash

    if not project_dir.exists():
        return TranscriptResult(commands=[], found=False)

    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not jsonl_files:
        return TranscriptResult(commands=[], found=False)

    commands = _parse_jsonl(jsonl_files[-1])
    return TranscriptResult(commands=commands, found=True)
