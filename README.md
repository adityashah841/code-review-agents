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

## Agents

| Agent | Role |
|---|---|
| Spec | Expands your plain-English spec into a precise function contract |
| Coder | Writes clean, typed Python from the expanded spec |
| Reviewer | Scores the code across correctness, security, style, complexity |
| Tester | Writes and executes a pytest suite against the generated code |
| Judge | Validates all outputs, detects misalignment, triggers targeted retries |

## Requirements

- Python 3.11+
- An Anthropic API key (get one at console.anthropic.com)

*Full documentation added as project is built.*
