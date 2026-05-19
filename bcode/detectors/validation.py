from __future__ import annotations
import subprocess
from typing import TYPE_CHECKING

from bcode.detectors.base import Finding, Severity
from bcode.git import DiffResult

if TYPE_CHECKING:
    from bcode.context import AuditContext

_DETECTOR = "validation"

RUNNERS: dict[str, list[str]] = {
    "test":      ["pytest", "jest", "vitest", "go test", "cargo test"],
    "lint":      ["ruff", "eslint", "golangci-lint", "rubocop"],
    "typecheck": ["mypy", "pyright", "tsc"],
    "build":     ["npm run build", "cargo build", "go build"],
}

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
    for line in stdout.splitlines():
        ll = line.lower()
        if "failed" in ll and "0 failed" not in ll:
            return True
        if "error:" in ll and "0 error" not in ll:
            return True
        if "assertionerror" in ll:
            return True
    return False


class ValidationDetector:
    name = "validation"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        if ctx.transcript is None or not ctx.transcript.found:
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.INFO,
                message="No transcript found — validation status unknown",
            ))
            return findings

        relevant = infer_relevant_categories(ctx.diff)

        for category in sorted(relevant):
            if category == "typecheck":
                if not ctx.config.run_typecheck:
                    ran = any(
                        command_matches_runner(cmd, runner)
                        for cmd in (c.command for c in ctx.transcript.commands)
                        for runner in RUNNERS["typecheck"]
                    )
                    if not ran:
                        findings.append(Finding(
                            detector=_DETECTOR,
                            severity=Severity.INFO,
                            message="typecheck not in session — run with --typecheck to verify",
                        ))
                # When run_typecheck=True, _run_typecheck_subprocess handles it below
                continue

            category_runners = RUNNERS.get(category, [])
            matched_commands = [
                c for c in ctx.transcript.commands
                if any(command_matches_runner(c.command, r) for r in category_runners)
            ]

            if not matched_commands:
                findings.append(Finding(
                    detector=_DETECTOR,
                    severity=Severity.FAIL,
                    message=f"no {category} runner found in session",
                ))
            else:
                for cmd in matched_commands:
                    if _stdout_suggests_failure(cmd.stdout):
                        findings.append(Finding(
                            detector=_DETECTOR,
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
        if result.returncode == 127:
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.INFO,
                message="mypy not installed — skipping typecheck",
            ))
        elif result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.FAIL,
                message=f"mypy found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))

    if ts_files:
        result = subprocess.run(
            ["tsc", "--noEmit", "--strict", *ts_files],
            capture_output=True, text=True, cwd=ctx.repo_root, check=False,
        )
        if result.returncode == 127:
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.INFO,
                message="tsc not installed — skipping typecheck",
            ))
        elif result.returncode != 0 and result.stdout.strip():
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.FAIL,
                message=f"tsc found type errors: {result.stdout.splitlines()[0]}",
                critical=True,
            ))

    return findings
