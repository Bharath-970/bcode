# bcode

**AI agent reliability scanner for Claude Code sessions.**

Detects hallucinated imports, missing validation, scope drift, and break-fix loops — before you commit.

```
bcode audit --task "fix login bug" --repo .
```

```
bcode audit — session report
─────────────────────────────────────────────
Task          : fix login bug
Files changed : 3
Transcript    : found

HALLUCINATION DETECTION
  ✓ No issues detected

VALIDATION ENFORCEMENT
  ✗ no test runner found in session
  ~ typecheck not in session — run with --typecheck to verify

SCOPE ANALYSIS [informational]
  ⚠ file outside task scope: config/settings.py

BREAK-FIX LOOPS
  ✓ No issues detected

─────────────────────────────────────────────
Reliability Score : 65 / 100   🟡 REVIEW RECOMMENDED
Recommendation    : Do not commit. Fix failing checks before committing.
─────────────────────────────────────────────
```

## Install

```bash
pip install bcode
```

Requires Python 3.10+.

## Usage

```bash
# Audit unstaged changes
bcode audit --task "your task description" --repo /path/to/repo

# Audit last N commits
bcode audit --task "fix auth bug" --commits 3

# Run type checking (mypy/tsc) as part of audit
bcode audit --task "refactor login" --typecheck

# JSON output for CI
bcode audit --task "add feature" --json | jq .score
```

Exits with code `1` when reliability score < 50 — use in CI pre-commit hooks.

## Detectors

| Detector | What it catches |
|---|---|
| **imports** | Python/JS imports that don't resolve locally or in `node_modules` |
| **validation** | Sessions where tests or linting weren't run |
| **scope** | Files edited outside the declared task scope |
| **breakfix** | Files touched across many commits (requires `--commits N`) |

## Risk score

Starts at 100. Each finding deducts points:

| Severity | Deduction |
|---|---|
| FAIL | −25 |
| WARN | −10 |
| INFO | 0 |

Any `critical` finding (e.g. hallucinated import confirmed) caps the score at 49.

## Configuration

Optional `.bcode.toml` in repo root:

```toml
run_typecheck = false
breakfix_warn_threshold = 3
breakfix_fail_threshold = 5
scope_drift_threshold = 0.40
protected_files = [".env", ".env.*", "*.lock", ".github/**", "*.pem", "*.key"]
```

## License

MIT
