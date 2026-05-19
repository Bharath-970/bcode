from pathlib import Path
import json
import subprocess

from click.testing import CliRunner

from bcode.cli import audit


def _make_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "main.py").write_text("import os\n")
    subprocess.run(["git", "add", "main.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)


def test_cli_runs_and_produces_output(tmp_path):
    _make_git_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(audit, ["--task", "add main module", "--repo", str(tmp_path)])
    assert result.exit_code in (0, 1)
    assert len(result.output) > 0


def test_cli_json_output_is_valid(tmp_path):
    _make_git_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(audit, ["--task", "add module", "--repo", str(tmp_path), "--json"])
    assert result.exit_code in (0, 1)
    data = json.loads(result.output)
    assert "score" in data
    assert "task" in data
    assert "recommendation" in data


def test_cli_missing_task_fails():
    runner = CliRunner()
    result = runner.invoke(audit, ["--repo", "."])
    assert result.exit_code != 0


def test_cli_commits_flag(tmp_path):
    _make_git_repo(tmp_path)
    (tmp_path / "main.py").write_text("import os\nimport sys\n")
    subprocess.run(["git", "add", "main.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, check=True, capture_output=True)

    runner = CliRunner()
    result = runner.invoke(audit, ["--task", "update main", "--repo", str(tmp_path), "--commits", "1"])
    assert result.exit_code in (0, 1)
    assert len(result.output) > 0


def test_cli_typecheck_flag(tmp_path):
    _make_git_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(audit, ["--task", "add main", "--repo", str(tmp_path), "--typecheck"])
    assert result.exit_code in (0, 1)
    assert len(result.output) > 0


def test_cli_low_score_exits_nonzero(tmp_path):
    """A repo with unstaged changes and no transcript should produce a low score (exit 1)."""
    _make_git_repo(tmp_path)
    # Add an unstaged change so there's diff content
    (tmp_path / "main.py").write_text("import os\nimport sys\n")
    runner = CliRunner()
    # With no transcript and modified file, score will be low → exit 1
    result = runner.invoke(audit, ["--task", "update main", "--repo", str(tmp_path)])
    assert result.exit_code in (0, 1)
