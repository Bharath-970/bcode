# bcode/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

# tomllib: stdlib in 3.11+; backport installed via pyproject.toml for 3.10
import tomllib

from bcode.git import DiffResult
from bcode.transcript import TranscriptResult


@dataclass
class BcodeConfig:
    run_typecheck: bool = False
    breakfix_warn_threshold: int = 3
    breakfix_fail_threshold: int = 5
    scope_drift_threshold: float = 0.40
    protected_files: list[str] = field(default_factory=lambda: [
        ".env", ".env.*", "*.lock", ".github/**", "*.pem", "*.key",
    ])


@dataclass
class AuditContext:
    diff: DiffResult
    task: str
    transcript: TranscriptResult | None = None
    repo_root: Path = field(default_factory=Path)
    config: BcodeConfig = field(default_factory=BcodeConfig)


def is_protected(path: Path, config: BcodeConfig) -> bool:
    name = path.name
    full = str(path)
    return any(
        fnmatch(name, pattern) or fnmatch(full, pattern)
        for pattern in config.protected_files
    )


def load_config(repo_root: Path) -> BcodeConfig:
    config_path = repo_root / ".bcode.toml"
    if not config_path.exists():
        return BcodeConfig()
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    cfg = data.get("bcode", {})
    return BcodeConfig(
        run_typecheck=cfg.get("run_typecheck", False),
        breakfix_warn_threshold=cfg.get("breakfix_warn_threshold", 3),
        breakfix_fail_threshold=cfg.get("breakfix_fail_threshold", 5),
        scope_drift_threshold=cfg.get("scope_drift_threshold", 0.40),
        protected_files=cfg.get("protected_files", BcodeConfig().protected_files),
    )
