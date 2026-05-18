from __future__ import annotations
from dataclasses import dataclass

from bcode.context import AuditContext
from bcode.detectors.base import Finding, Severity
from bcode.detectors.breakfix import BreakfixDetector
from bcode.detectors.imports import ImportsDetector
from bcode.detectors.scope import ScopeDetector
from bcode.detectors.validation import ValidationDetector, infer_relevant_categories

_DETECTORS = [ImportsDetector(), ValidationDetector(), ScopeDetector(), BreakfixDetector()]

_WEIGHTS = {Severity.FAIL: 25, Severity.WARN: 10, Severity.INFO: 0}


def risk_score(findings: list[Finding]) -> int:
    score = 100
    for f in findings:
        score -= _WEIGHTS[f.severity]
    if any(f.critical for f in findings):
        score = min(score, 49)
    return max(0, score)


def build_recommendation(findings: list[Finding]) -> str:
    criticals = [f for f in findings if f.critical]
    fails = [f for f in findings if f.severity == Severity.FAIL and not f.critical]
    warns = [f for f in findings if f.severity == Severity.WARN]
    if criticals:
        reasons = "; ".join(f.message for f in criticals)
        return f"Do not commit. {reasons}."
    if fails:
        return "Do not commit. Fix failing checks before committing."
    if warns:
        return "Review flagged files before committing."
    return "Session looks clean. Proceed."


@dataclass
class AuditResult:
    task: str
    findings: list[Finding]
    score: int
    files_changed: int
    transcript_found: bool
    relevant_categories: set[str]
    recommendation: str


def run(ctx: AuditContext) -> AuditResult:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector.run(ctx))

    score = risk_score(findings)
    return AuditResult(
        task=ctx.task,
        findings=findings,
        score=score,
        files_changed=len(ctx.diff.files),
        transcript_found=ctx.transcript.found if ctx.transcript else False,
        relevant_categories=infer_relevant_categories(ctx.diff),
        recommendation=build_recommendation(findings),
    )
