# bcode

`bcode` is a reliability scanner for AI-assisted coding sessions.

It inspects your repo diff, recent commit history, and available session transcript
data to catch the boring but expensive failures that sneak in right before commit:

- hallucinated or unresolved imports
- missing validation and skipped checks
- scope drift outside the declared task
- break-fix churn across repeated commits

If an agent says "should work now," `bcode` is the part that asks for evidence.

## What it does

`bcode audit` scores the current work session out of 100 and prints a commit
recommendation based on the findings.

```bash
bcode audit --task "fix login bug" --repo .
```

Example terminal report:

```text
bcode audit - session report
---------------------------------------------
Task          : fix login bug
Files changed : 3
Transcript    : found

HALLUCINATION DETECTION
  OK No issues detected

VALIDATION ENFORCEMENT
  FAIL no test runner found in session
  WARN typecheck not in session - run with --typecheck to verify

SCOPE ANALYSIS
  WARN file outside task scope: config/settings.py

BREAK-FIX LOOPS
  OK No issues detected

---------------------------------------------
Reliability Score : 65 / 100
Recommendation    : Do not commit. Fix failing checks before committing.
---------------------------------------------
```

## Install

Right now the reliable install path is from source.

```bash
git clone https://github.com/Bharath-970/bcode.git
cd bcode
python3.11 -m pip install .
```

If you want an isolated CLI environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

Requires Python 3.10+.

## Quick start

Audit unstaged changes in the current repo:

```bash
bcode audit --task "repair auth token refresh" --repo .
```

Audit the last 3 commits instead of the current unstaged diff:

```bash
bcode audit --task "stabilize retry flow" --repo . --commits 3
```

Include typecheck evidence in the session audit:

```bash
bcode audit --task "refactor login controller" --repo . --typecheck
```

Emit machine-readable JSON for CI or hooks:

```bash
bcode audit --task "ship billing fix" --repo . --json
```

Show verbose findings with file paths:

```bash
bcode audit --task "trim onboarding scope" --repo . --verbose
```

## CLI

```text
bcode audit --task TEXT [--commits N] [--typecheck] [--repo PATH] [--json] [--verbose]
```

Options:

- `--task`, `-t`: required declared task description
- `--commits`, `-c`: inspect the last `N` commits instead of the unstaged diff
- `--typecheck`: run supported typecheckers as part of validation analysis
- `--repo`: repo root to inspect, defaults to the current directory
- `--json`: output structured JSON instead of terminal text
- `--verbose`, `-v`: include individual findings in terminal output

## Signals and detectors

| Detector | What it catches |
|---|---|
| `imports` | Python or JS imports that do not resolve locally or in `node_modules` |
| `validation` | Sessions with missing tests, missing lint/typecheck evidence, or weak verification |
| `scope` | Files that drift outside the declared task scope |
| `breakfix` | Repeated edits to the same files across recent commits |

## Scoring

The score starts at `100`.

| Severity | Deduction |
|---|---|
| `FAIL` | -25 |
| `WARN` | -10 |
| `INFO` | 0 |

Any critical finding caps the score at `49`, which is the tool's way of saying
"no, you are not done."

If the final score is below `50`, `bcode` exits with status code `1`. That makes
it easy to wire into CI, pre-push hooks, or local quality gates.

## Configuration

You can configure repository-specific behavior with an optional `.bcode.toml`
file in the repo root:

```toml
run_typecheck = false
breakfix_warn_threshold = 3
breakfix_fail_threshold = 5
scope_drift_threshold = 0.40
protected_files = [".env", ".env.*", "*.lock", ".github/**", "*.pem", "*.key"]
```

## Typical workflow

1. Make your changes.
2. Describe the task explicitly with `--task`.
3. Run `bcode audit`.
4. Fix any `FAIL` or high-signal `WARN` findings.
5. Re-run until the recommendation is no longer telling you to stop lying to yourself.

## Development

Run tests from the repo root with a Python 3.10+ environment:

```bash
python -m pytest -q
```

Build distribution artifacts:

```bash
python -m pip install build
python -m build
```

## License

MIT
