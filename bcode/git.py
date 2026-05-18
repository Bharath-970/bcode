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
