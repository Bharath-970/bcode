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
