# bcode/detectors/validation.py
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from bcode.detectors.base import Detector, Finding, Severity
from bcode.git import DiffResult

if TYPE_CHECKING:
    from bcode.context import AuditContext

RUNNERS: dict[str, list[str]] = {
    "test":      ["pytest", "jest", "vitest", "go test", "cargo test"],
    "lint":      ["ruff", "eslint", "golangci-lint", "rubocop"],
    "typecheck": ["mypy", "pyright", "tsc"],
    "build":     ["npm run build", "cargo build", "go build"],
}

FAILURE_INDICATORS = {"FAILED", "error:", "AssertionError", "ERROR"}

_EXT_CATEGORIES: dict[str, set[str]] = {
    ".py":  {"test", "lint", "typecheck"},
    ".ts":  {"test", "lint", "typecheck", "build"},
    ".tsx": {"test", "lint", "typecheck", "build"},
    ".js":  {"test", "lint", "typecheck", "build"},
    ".jsx": {"test", "lint", "typecheck", "build"},
    ".go":  {"test", "build"},
}


def infer_relevant_categories(diff: DiffResult) -> set[str]:
    categories: set[str] = set()
    for f in diff.files:
        categories.update(_EXT_CATEGORIES.get(f.path.suffix, set()))
    return categories


def command_matches_runner(command: str, runner: str) -> bool:
    argv = command.strip().split()
    if not argv:
        return False
    runner_tokens = runner.split()
    return argv[: len(runner_tokens)] == runner_tokens


def _stdout_suggests_failure(stdout: str) -> bool:
    return any(indicator in stdout for indicator in FAILURE_INDICATORS)


class ValidationDetector:
    name = "validation"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        if ctx.transcript is None or not ctx.transcript.found:
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="No transcript found — validation status unknown",
            ))
            return findings

        relevant = infer_relevant_categories(ctx.diff)
        commands_run = [c.command for c in ctx.transcript.commands]

        for category in sorted(relevant):
            if category == "typecheck" and not ctx.config.run_typecheck:
                ran = any(
                    command_matches_runner(cmd, runner)
                    for cmd in commands_run
                    for runner in RUNNERS["typecheck"]
                )
                if not ran:
                    findings.append(Finding(
                        detector="validation",
                        severity=Severity.INFO,
                        message="typecheck not in session — run with --typecheck to verify",
                    ))
                continue

            category_runners = RUNNERS.get(category, [])
            matched_commands = [
                c for c in ctx.transcript.commands
                if any(command_matches_runner(c.command, r) for r in category_runners)
            ]

            if not matched_commands:
                findings.append(Finding(
                    detector="validation",
                    severity=Severity.FAIL,
                    message=f"no {category} runner found in session",
                ))
            else:
                for cmd in matched_commands:
                    if _stdout_suggests_failure(cmd.stdout):
                        findings.append(Finding(
                            detector="validation",
                            severity=Severity.WARN,
                            message=f"{cmd.command.split()[0]} ran — stdout suggests failures (verify manually)",
                        ))

        if ctx.config.run_typecheck:
            findings.extend(_run_typecheck_subprocess(ctx))

        return findings


def _run_typecheck_subprocess(ctx: "AuditContext") -> list[Finding]:
    findings: list[Finding] = []
    py_files = [
        str(f.path) for f in ctx.diff.files if f.path.suffix == ".py"
    ]
    ts_files = [
        str(f.path) for f in ctx.diff.files if f.path.suffix in {".ts", ".tsx"}
    ]

    if py_files:
        result = subprocess.run(
            ["mypy", "--no-error-summary", *py_files],
            capture_output=True, text=True, cwd=ctx.repo_root, check=False,
        )
        if result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector="validation",
                severity=Severity.FAIL,
                message=f"mypy found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))
        elif result.returncode == 127:  # command not found
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="mypy not installed — skipping typecheck",
            ))

    if ts_files:
        result = subprocess.run(
            ["tsc", "--noEmit", "--strict", *ts_files],
            capture_output=True, text=True, cwd=ctx.repo_root, check=False,
        )
        if result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector="validation",
                severity=Severity.FAIL,
                message=f"tsc found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))
        elif result.returncode == 127:
            findings.append(Finding(
                detector="validation",
                severity=Severity.INFO,
                message="tsc not installed — skipping typecheck",
            ))

    return findings
