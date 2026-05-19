from __future__ import annotations
import dataclasses
import json
import sys
import time
import click
from bcode.audit import AuditResult
from bcode.detectors.base import Severity

_LOGO = [
    "  _     ___  ___  ___  ___ ",
    " | |__ / __||   \\| __||   \\",
    " | '_ \\ (__ | |) | _| | |) |",
    " |_.__/\\___||___/|___||___/ ",
    "   AI Agent Reliability Scanner",
]

# Color sweep cycles — each frame shifts the gradient down one line
_SWEEP = [
    ["white",          "bright_magenta", "magenta",      "bright_cyan",   "cyan"],
    ["bright_magenta", "magenta",        "bright_cyan",  "cyan",          "bright_blue"],
    ["magenta",        "bright_cyan",    "cyan",         "bright_blue",   "blue"],
    ["bright_cyan",    "cyan",           "bright_blue",  "blue",          "bright_magenta"],
    ["cyan",           "bright_blue",    "blue",         "bright_magenta","magenta"],
    ["bright_blue",    "blue",           "bright_magenta","magenta",      "bright_cyan"],
    # settle on final
    ["bright_magenta", "magenta",        "bright_cyan",  "cyan",          "bright_blue"],
]

_DETECTORS = [
    ("imports",    "IMPORTS    "),
    ("validation", "VALIDATION "),
    ("scope",      "SCOPE      "),
    ("breakfix",   "BREAK-FIX  "),
]


def _supports_unicode() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return enc.lower() in ("utf-8", "utf8")


def _c(text: str, color: str, bold: bool = False) -> str:
    return click.style(text, fg=color, bold=bold)


def _score_bar(score: int) -> str:
    filled = score // 5
    empty = 20 - filled
    if score >= 80:
        color = "bright_green"
    elif score >= 50:
        color = "bright_yellow"
    else:
        color = "bright_red"
    bar = _c("█" * filled, color) + _c("░" * empty, "bright_black")
    return bar


def _score_label(score: int) -> str:
    if score >= 80:
        return _c(f"{score}/100  LOW RISK", "bright_green", bold=True)
    if score >= 50:
        return _c(f"{score}/100  REVIEW", "bright_yellow", bold=True)
    return _c(f"{score}/100  HIGH RISK", "bright_red", bold=True)


def _finding_icon(sev: Severity) -> str:
    if sev == Severity.FAIL:
        return _c("✗", "bright_red", bold=True)
    if sev == Severity.WARN:
        return _c("⚠", "bright_yellow", bold=True)
    return _c("~", "bright_black")


def _detector_summary(findings: list) -> str:
    if not findings:
        return _c("✓  clean", "bright_green")
    fails  = [f for f in findings if f.severity == Severity.FAIL]
    warns  = [f for f in findings if f.severity == Severity.WARN]
    infos  = [f for f in findings if f.severity == Severity.INFO]
    if fails:
        msgs = "  ·  ".join(f.message for f in fails[:2])
        suffix = f"  (+{len(fails)-2} more)" if len(fails) > 2 else ""
        return _c(f"✗  {msgs}{suffix}", "bright_red")
    if warns:
        msgs = "  ·  ".join(f.message for f in warns[:2])
        suffix = f"  (+{len(warns)-2} more)" if len(warns) > 2 else ""
        return _c(f"⚠  {msgs}{suffix}", "bright_yellow")
    return _c(f"~  {infos[0].message}", "bright_black")


def _render_logo() -> None:
    is_tty = sys.stdout.isatty()
    click.echo()

    if is_tty:
        # Print first frame
        for line, color in zip(_LOGO, _SWEEP[0]):
            sys.stdout.write("  " + click.style(line, fg=color, bold=True) + "\n")
        sys.stdout.flush()

        # Sweep through frames
        for frame in _SWEEP[1:]:
            time.sleep(0.07)
            # Move cursor back up
            sys.stdout.write(f"\033[{len(_LOGO)}A")
            for line, color in zip(_LOGO, frame):
                sys.stdout.write("  " + click.style(line, fg=color, bold=True) + "\n")
            sys.stdout.flush()
    else:
        for line, color in zip(_LOGO, _SWEEP[-1]):
            click.echo("  " + click.style(line, fg=color, bold=True))

    click.echo()


def _sep(char: str = "━", width: int = 52) -> str:
    return _c(char * width, "bright_black")


def _render_terminal(result: AuditResult, verbose: bool = False) -> None:
    uni = _supports_unicode()

    _render_logo()

    # Meta row
    transcript_status = (
        _c("transcript ✓", "bright_green") if result.transcript_found
        else _c("no transcript", "bright_black")
    )
    click.echo(
        f"  {_c('task', 'bright_black')}   {_c(result.task, 'white', bold=True)}\n"
        f"  {_c('files', 'bright_black')}  {_c(str(result.files_changed), 'white')} changed"
        f"  ·  {transcript_status}"
    )
    click.echo()
    click.echo("  " + _sep())
    click.echo()

    by_detector: dict[str, list] = {}
    for f in result.findings:
        by_detector.setdefault(f.detector, []).append(f)

    # Summary table
    for key, label in _DETECTORS:
        findings = by_detector.get(key, [])
        summary = _detector_summary(findings)
        click.echo(f"  {_c(label, 'white', bold=True)}  {summary}")

        if verbose and findings:
            for f in findings:
                icon = _finding_icon(f.severity)
                loc = _c(f"  {f.file}", "bright_black") if f.file else ""
                click.echo(f"    {icon}  {f.message}{loc}")
        click.echo()

    click.echo("  " + _sep())
    click.echo()

    # Score bar
    bar = _score_bar(result.score)
    label = _score_label(result.score)
    click.echo(f"  {_c('score', 'bright_black')}  {bar}  {label}")
    click.echo()

    # Recommendation
    if result.score < 50:
        rec_color = "bright_red"
        prefix = "✗"
    elif result.score < 80:
        rec_color = "bright_yellow"
        prefix = "⚠"
    else:
        rec_color = "bright_green"
        prefix = "✓"

    click.echo(f"  {_c(prefix, rec_color, bold=True)}  {_c(result.recommendation, rec_color)}")
    click.echo()
    click.echo("  " + _sep())
    click.echo()


def _render_json(result: AuditResult) -> None:
    data = dataclasses.asdict(result)
    data["relevant_categories"] = sorted(result.relevant_categories)
    print(json.dumps(data, indent=2, default=str))


def render(result: AuditResult, output_json: bool = False, verbose: bool = False) -> None:
    if output_json:
        _render_json(result)
    else:
        _render_terminal(result, verbose=verbose)
