from __future__ import annotations
import dataclasses
import json
import sys
from bcode.audit import AuditResult
from bcode.detectors.base import Severity


def _supports_unicode() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return enc.lower() in ("utf-8", "utf8")


def _get_symbols() -> dict[str, str]:
    if _supports_unicode():
        return {
            "pass": "✓", "fail": "✗", "warn": "⚠",
            "red": "🔴", "yellow": "🟡", "green": "🟢",
        }
    return {
        "pass": "OK", "fail": "XX", "warn": "!",
        "red": "[RED]", "yellow": "[YELLOW]", "green": "[GREEN]",
    }


def _score_band(score: int, sym: dict[str, str]) -> str:
    if score >= 80:
        return f"{sym['green']} LOW RISK"
    if score >= 50:
        return f"{sym['yellow']} REVIEW RECOMMENDED"
    return f"{sym['red']} HIGH RISK"


def _render_terminal(result: AuditResult) -> None:
    sym = _get_symbols()
    sep = "─" * 45

    print("bcode audit — session report")
    print(sep)
    print(f"Task          : {result.task}")
    print(f"Files changed : {result.files_changed}")
    status = "found" if result.transcript_found else "not found (validation partial)"
    print(f"Transcript    : {status}")
    print()

    by_detector: dict[str, list] = {}
    for f in result.findings:
        by_detector.setdefault(f.detector, []).append(f)

    _render_section("HALLUCINATION DETECTION", by_detector.get("imports", []), sym)
    _render_section("VALIDATION ENFORCEMENT", by_detector.get("validation", []), sym)
    _render_section("SCOPE ANALYSIS [informational]", by_detector.get("scope", []), sym)
    _render_section("BREAK-FIX LOOPS", by_detector.get("breakfix", []), sym)

    print(sep)
    band = _score_band(result.score, sym)
    print(f"Reliability Score : {result.score} / 100   {band}")
    print(f"Recommendation    : {result.recommendation}")
    print(sep)


def _render_section(title: str, findings: list, sym: dict[str, str]) -> None:
    print(title)
    if not findings:
        print(f"  {sym['pass']} No issues detected")
    for f in findings:
        icon = sym["fail"] if f.severity == Severity.FAIL else (
            sym["warn"] if f.severity == Severity.WARN else "~"
        )
        loc = f" — {f.file}" if f.file else ""
        print(f"  {icon} {f.message}{loc}")
    print()


def _render_json(result: AuditResult) -> None:
    data = dataclasses.asdict(result)
    data["relevant_categories"] = sorted(result.relevant_categories)
    print(json.dumps(data, indent=2, default=str))


def render(result: AuditResult, output_json: bool = False) -> None:
    if output_json:
        _render_json(result)
    else:
        _render_terminal(result)
