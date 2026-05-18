from __future__ import annotations
from typing import TYPE_CHECKING

from bcode.detectors.base import Finding, Severity

if TYPE_CHECKING:
    from bcode.context import AuditContext

_DETECTOR = "breakfix"


class BreakfixDetector:
    name = "breakfix"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []

        if all(f.commit_count == 0 for f in ctx.diff.files):
            findings.append(Finding(
                detector=_DETECTOR,
                severity=Severity.INFO,
                message="break-fix detection requires --commits flag",
            ))
            return findings

        warn_t = ctx.config.breakfix_warn_threshold
        fail_t = ctx.config.breakfix_fail_threshold

        for changed in ctx.diff.files:
            c = changed.commit_count
            if c >= fail_t:
                findings.append(Finding(
                    detector=_DETECTOR,
                    severity=Severity.FAIL,
                    message=(
                        f"{changed.path} patched {c} times across {c} commits "
                        f"(threshold: {fail_t})"
                    ),
                    file=changed.path,
                ))
            elif c >= warn_t:
                findings.append(Finding(
                    detector=_DETECTOR,
                    severity=Severity.WARN,
                    message=(
                        f"{changed.path} patched {c} times across {c} commits "
                        f"(threshold: {warn_t})"
                    ),
                    file=changed.path,
                ))

        return findings
