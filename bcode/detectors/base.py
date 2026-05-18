# bcode/detectors/base.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from bcode.context import AuditContext


class Severity(Enum):
    INFO = "info"   # no score impact
    WARN = "warn"   # -10 pts
    FAIL = "fail"   # -25 pts


@dataclass(frozen=True)
class Finding:
    detector: str       # "imports" | "validation" | "scope" | "breakfix"
    severity: Severity
    message: str
    file: Path | None = None
    critical: bool = False  # True → score capped at 49 regardless of total


class Detector(Protocol):
    @property
    def name(self) -> str: ...

    def run(self, ctx: "AuditContext") -> list[Finding]: ...
