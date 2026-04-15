# code-review-agents

> A self-correcting multi-agent CLI for automated Python code review.

**Status:** Under construction — see checkpoints below.

## What it does

Three specialized AI agents — Coder, Reviewer, and Tester — collaborate to generate,
review, and test Python code from a plain English spec. A fourth Judge agent supervises
all three, detects misaligned or invalid outputs, and triggers targeted retries.

## Quick start

```bash
pip install uv
uv sync
python cli.py --spec "sort a list of integers" --name sorter
```

## Agents in detail

### Spec agent
Converts your plain-English spec into a precise JSON function contract: function name,
argument types, return type, edge cases, and an example call. Shown to you for
confirmation before any code is generated — preventing misaligned outputs from the start.

### Coder agent
Receives the confirmed contract and writes clean, typed, stdlib-only Python with a
Google-style docstring. Handles every edge case from the contract. On Judge retry,
receives a targeted correction hint describing exactly what to fix.

### Reviewer agent
Reads the generated code and returns structured JSON: scores (0–10) for correctness,
security, style, and complexity; a list of issues with line numbers and severity;
and top improvement recommendations. On Judge retry, receives a targeted correction hint.

### Tester agent
Writes a complete pytest file that imports from the generated module. Covers happy path,
edge cases, and exception cases. The orchestrator executes the tests with subprocess
and feeds pass/fail results into the Judge's assessment.

### Judge agent
Validates all three outputs before the report is generated. Runs two free checks first:
`ast.parse()` on both the code and the test file to catch syntax errors without an API
call. Then runs an LLM check that verifies the tests actually import the real module and
function names, the reviewer's line numbers are real, and the code fulfills the spec.

If any agent fails the Judge, only that agent re-runs — with a targeted correction hint
explaining exactly what went wrong. Maximum 2 retries per agent per pipeline run.

## Requirements

- Python 3.11+
- An Anthropic API key (get one at console.anthropic.com)

*Full documentation added as project is built.*

## API key

Pass your key with `--api-key` or set the environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python cli.py --spec "sort a list" --name sorter
```

The key is never stored to disk. It is passed at runtime and held only in memory
for the duration of the run.
