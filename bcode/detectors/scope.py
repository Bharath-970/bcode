from __future__ import annotations
from typing import TYPE_CHECKING

from bcode.context import is_protected
from bcode.detectors.base import Finding, Severity

if TYPE_CHECKING:
    from bcode.context import AuditContext
    from bcode.git import ChangedFile

STOPWORDS = frozenset({
    "fix", "add", "the", "a", "an", "in", "on", "for", "to",
    "and", "or", "with", "update", "change", "make", "get",
    "set", "use", "remove", "delete", "create", "from", "into",
    "bug", "issue", "error", "problem", "broken", "feature",
})

_DETECTOR = "scope"


def _tokenize_task(task: str) -> set[str]:
    return {t for t in task.lower().split() if t not in STOPWORDS}


def _is_in_scope_by_name(changed: ChangedFile, tokens: set[str]) -> bool:
    path_str = str(changed.path).lower()
    return any(token in path_str for token in tokens)


def _is_in_scope(changed: ChangedFile, tokens: set[str], in_scope_dirs: set[str]) -> bool:
    return _is_in_scope_by_name(changed, tokens) or str(changed.path.parent) in in_scope_dirs


class ScopeDetector:
    name = "scope"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        for changed in ctx.diff.files:
            if is_protected(changed.path, ctx.config):
                findings.append(Finding(
                    detector=_DETECTOR,
                    severity=Severity.WARN,
                    message=f"protected file modified: {changed.path}",
                    file=changed.path,
                ))

        tokens = _tokenize_task(ctx.task)
        if not tokens:
            return findings

        in_scope_by_name = [f for f in ctx.diff.files if _is_in_scope_by_name(f, tokens)]
        in_scope_dirs = {str(f.path.parent) for f in in_scope_by_name}

        out_of_scope = [f for f in ctx.diff.files if not _is_in_scope(f, tokens, in_scope_dirs)]
        total = len(ctx.diff.files)
        if total == 0:
            return findings

        ratio = len(out_of_scope) / total
        threshold = (
            0.60
            if any(f.commit_count > 0 for f in ctx.diff.files)
            else ctx.config.scope_drift_threshold
        )

        if ratio > threshold:
            for changed in out_of_scope:
                findings.append(Finding(
                    detector=_DETECTOR,
                    severity=Severity.WARN,
                    message=f"file outside task scope: {changed.path}",
                    file=changed.path,
                ))

        return findings
