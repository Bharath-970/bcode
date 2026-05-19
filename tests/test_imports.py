# tests/test_imports.py
from pathlib import Path
from bcode.detectors.imports import ImportsDetector
from bcode.detectors.base import Severity
from bcode.git import DiffResult, ChangedFile
from bcode.context import AuditContext


def _ctx(added_lines: list[str], repo_root: Path) -> AuditContext:
    cf = ChangedFile(
        path=Path("src/auth.py"),
        added_lines=added_lines,
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=repo_root)
    return AuditContext(diff=diff, task="fix login", repo_root=repo_root)


def test_hallucinated_python_import_detected(tmp_path):
    # 'jose' is not installed; python-jose is (different package name)
    ctx = _ctx(["import jose", "from jose import jwt"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert any(f.severity == Severity.FAIL and f.critical and "jose" in f.message
               for f in findings)


def test_stdlib_import_not_flagged(tmp_path):
    ctx = _ctx(["import os", "from pathlib import Path"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_local_module_import_not_flagged(tmp_path):
    # Create local module structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth").mkdir()
    (tmp_path / "src" / "auth" / "utils.py").write_text("")
    ctx = _ctx(["from src.auth.utils import validate_token"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_dunder_import_skipped(tmp_path):
    ctx = _ctx(["from __future__ import annotations"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_relative_import_skipped(tmp_path):
    ctx = _ctx(["from . import helpers", "from .utils import parse"], tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_scoped_package_resolved(tmp_path):
    pkg_dir = tmp_path / "node_modules" / "@radix-ui" / "react-button"
    pkg_dir.mkdir(parents=True)
    cf = ChangedFile(
        path=Path("app/Button.tsx"),
        added_lines=["import { Button } from '@radix-ui/react-button'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="add button", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_missing_scoped_package_flagged(tmp_path):
    cf = ChangedFile(
        path=Path("app/Button.tsx"),
        added_lines=["import { x } from '@missing/package'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="add button", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert any(f.severity == Severity.FAIL and "@missing/package" in f.message
               for f in findings)


def test_js_subpath_import_resolved(tmp_path):
    # 'clsx/lite' → check node_modules/clsx
    (tmp_path / "node_modules" / "clsx").mkdir(parents=True)
    cf = ChangedFile(
        path=Path("app/util.ts"),
        added_lines=["import { clsx } from 'clsx/lite'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="fix styles", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []


def test_js_relative_import_skipped(tmp_path):
    cf = ChangedFile(
        path=Path("app/util.ts"),
        added_lines=["import { x } from './helpers'", "import y from '../base'"],
        removed_lines=[],
        commit_count=0,
    )
    diff = DiffResult(files=[cf], repo_root=tmp_path)
    ctx = AuditContext(diff=diff, task="fix", repo_root=tmp_path)
    findings = ImportsDetector().run(ctx)
    assert findings == []
