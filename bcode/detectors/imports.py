# bcode/detectors/imports.py
from __future__ import annotations
import importlib.util
import re
from pathlib import Path
from typing import TYPE_CHECKING

from bcode.detectors.base import Detector, Finding, Severity

if TYPE_CHECKING:
    from bcode.context import AuditContext

_PY_EXTENSIONS = {".py"}
_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
_SKIP_PREFIXES = (".", "__")

_PY_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import)"
)
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""
)


def _is_local_module(name: str, repo_root: Path) -> bool:
    base = name.split(".")[0]
    return (repo_root / base).is_dir() or (repo_root / f"{base}.py").exists()


def _resolve_python(module: str) -> bool:
    try:
        spec = importlib.util.find_spec(module)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _resolve_js(specifier: str, repo_root: Path) -> bool:
    if specifier.startswith("."):
        return True  # relative — skip
    if specifier.startswith("@"):
        parts = specifier.split("/")
        if len(parts) < 2:
            return True  # malformed — skip
        base = f"{parts[0]}/{parts[1]}"
    else:
        base = specifier.split("/")[0]
    return (repo_root / "node_modules" / base).exists()


def _check_python_lines(
    lines: list[str], file_path: Path, repo_root: Path
) -> list[Finding]:
    findings: list[Finding] = []
    for line in lines:
        m = _PY_IMPORT_RE.match(line)
        if not m:
            continue
        module = m.group(1) or m.group(2)
        if not module:
            continue
        root = module.split(".")[0]
        if root.startswith(_SKIP_PREFIXES):
            continue
        if _is_local_module(root, repo_root):
            continue
        if not _resolve_python(root):
            findings.append(Finding(
                detector="imports",
                severity=Severity.FAIL,
                message=f"import '{module}' not found in environment",
                file=file_path,
                critical=True,
            ))
    return findings


def _check_js_lines(
    lines: list[str], file_path: Path, repo_root: Path
) -> list[Finding]:
    findings: list[Finding] = []
    for line in lines:
        for specifier in _JS_IMPORT_RE.findall(line):
            if _resolve_js(specifier, repo_root):
                continue
            findings.append(Finding(
                detector="imports",
                severity=Severity.FAIL,
                message=f"import '{specifier}' not found in node_modules",
                file=file_path,
                critical=True,
            ))
    return findings


class ImportsDetector:
    name = "imports"

    def run(self, ctx: "AuditContext") -> list[Finding]:
        findings: list[Finding] = []
        for changed in ctx.diff.files:
            ext = changed.path.suffix
            if ext in _PY_EXTENSIONS:
                findings.extend(
                    _check_python_lines(changed.added_lines, changed.path, ctx.repo_root)
                )
            elif ext in _JS_EXTENSIONS:
                findings.extend(
                    _check_js_lines(changed.added_lines, changed.path, ctx.repo_root)
                )
        return findings
