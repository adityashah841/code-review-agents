# code-review-agents

> A self-correcting multi-agent CLI for automated Python code review.

[![CI](https://github.com/adityashah841/code-review-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/adityashah841/code-review-agents/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

Three specialized AI agents — **Coder**, **Reviewer**, and **Tester** — collaborate
to generate, review, and test Python code from a plain-English spec. A fourth **Judge**
agent supervises all three, detects misaligned outputs, and triggers targeted retries.

All you need is an Anthropic API key.

---

## Demo

```bash
python cli.py review --spec "binary search on a sorted list" --name binary_search
```

```
code-review-agents
Spec: binary search on a sorted list

[Spec] Expanding spec contract...
[Coder] Generating code...
[Reviewer + Tester] Running in parallel...
[Runner] Executing pytest...
[Judge] Evaluating all outputs...
[Judge] All agents passed.

┌─────────────────────────────┐
│       Review scores         │
├─────────────┬───────┬───────┤
│ Correctness │  9/10 │ Excellent │
│ Security    │  9/10 │ Excellent │
│ Style       │  8/10 │ Good      │
│ Complexity  │  7/10 │ Good      │
└─────────────┴───────┴───────┘

Tests: PASSED  |  Judge retries: 0  |  Tokens: 1842in / 987out
Report saved to reports/review.md
```

---

## How it works

```
Your spec (plain English)
        ↓
[Spec agent]  expands to a precise JSON function contract
        ↓
[Coder agent]  writes clean typed Python to workspace/
        ↓
[Reviewer] ──┐  run in parallel via asyncio.gather()
[Tester]  ───┘  tests written and executed with pytest
        ↓
[Judge agent]  validates alignment across all outputs
    ├── PASS → Markdown report generated
    └── FAIL → targeted retry with correction hint (max 2×)
```

The Reviewer and Tester always run in parallel. Total wall-clock time equals the
slower of the two, not their sum.

---

## Agents

| Agent | Role |
|---|---|
| **Spec** | Expands plain-English to a precise JSON contract: function name, types, edge cases |
| **Coder** | Writes clean, typed, stdlib-only Python from the contract |
| **Reviewer** | Scores correctness, security, style, and complexity with line-level issues |
| **Tester** | Writes and executes a pytest suite covering happy path, edge cases, exceptions |
| **Judge** | Validates alignment, catches hallucinated imports, triggers targeted retries |

---

## Quick start

### Prerequisites

- Python 3.11+
- An Anthropic API key — get one free at [console.anthropic.com](https://console.anthropic.com)

### Install

```bash
git clone https://github.com/adityashah841/code-review-agents
cd code-review-agents
pip install uv
uv sync
```

### Run a review

```bash
# Set your key once
export ANTHROPIC_API_KEY="sk-ant-..."

# Review any plain-English spec
python cli.py review --spec "sort a list of integers" --name sorter
python cli.py review --spec "validate an email address" --name email_validator
python cli.py review --spec "implement an LRU cache" --name lru_cache

# Stream the Coder output live
python cli.py review --spec "binary search" --name binary_search --stream

# Pass your key directly (useful for one-off runs)
python cli.py review --spec "reverse a string" --name reverser --api-key sk-ant-...
```

### View run history

```bash
python cli.py history
python cli.py history --limit 5
```

### Run with Docker

```bash
# Set your key and run
export ANTHROPIC_API_KEY="sk-ant-..."
docker compose run review --spec "sort a list" --name sorter
```

---

## CLI reference

```
python cli.py review [OPTIONS]

  -s, --spec TEXT      Plain-English function spec  [required]
  -n, --name TEXT      Output module name  [default: module]
  -o, --output TEXT    Markdown report path  [default: reports/review.md]
  -k, --api-key TEXT   Anthropic API key (or set ANTHROPIC_API_KEY)
  -m, --model TEXT     Model to use for all agents  [default: claude-opus-4-5]
  --stream             Stream Coder output token-by-token
  -y, --yes            Skip spec confirmation prompt

python cli.py history [OPTIONS]

  -n, --limit INTEGER  Number of recent runs to show  [default: 20]
```

---

## Output

Every run produces a Markdown report in `reports/` with:

- Overall score and per-category breakdown (correctness, security, style, complexity)
- Line-level issues sorted by severity (high / medium / low)
- Top improvement recommendations
- Full pytest output
- The expanded spec contract JSON
- Token usage and Judge retry count

Run history is persisted locally in `runs.db` (SQLite).

---

## Project structure

```
code-review-agents/
├── agents/
│   ├── base_agent.py       Shared API wrapper with retry, streaming, token tracking
│   ├── spec_agent.py       Spec expansion agent
│   ├── coder_agent.py      Code generation agent
│   ├── reviewer_agent.py   Code review agent
│   ├── tester_agent.py     Test generation agent
│   └── judge_agent.py      Output validation and retry orchestration
├── orchestrator.py         Pipeline: Spec → Coder → Reviewer+Tester → Judge → Report
├── cli.py                  Click CLI: review, history commands
├── report_generator.py     Markdown report writer
├── history.py              SQLite run history
├── tests/                  Full test suite (mocked — no real API calls)
└── workspace/              Generated .py files (gitignored)
```

---

## Model benchmark — stress test results

The same five specs were run against two models to compare quality, reliability, and cost.
All runs used live Anthropic API calls with no human intervention.

### Specs used

| # | Spec | Complexity |
|---|---|---|
| 1 | Check if a number is prime | Simple |
| 2 | Recursive descent arithmetic expression parser (+, -, *, /, parentheses, precedence) | Medium |
| 3 | LRU cache with doubly linked list + hashmap, O(1) get/put, eviction | Medium-Hard |
| 4 | Trie with insert, search, starts_with, delete | Hard |
| 5 | Weighted directed graph with Dijkstra, DFS, BFS, cycle detection | Hard |

---

### claude-opus-4-6

| Spec | Score | Tests | Judge retries | Tokens (in/out) |
|---|---|---|---|---|
| is_prime | **9.8/10** | PASSED ✅ | 0 | 5,344 / 3,192 |
| expr_parser | **8.3/10** | PASSED ✅ | 0 | 11,725 / 6,698 |
| lru_cache | **9.0/10** | PASSED ✅ | 0 | 9,627 / 5,342 |
| trie | **9.0/10** | PASSED ✅ | 0 | 9,639 / 5,673 |
| graph | **9.3/10** | PASSED ✅ | 0 | 14,147 / 7,392 |
| **Average** | **9.1/10** | **5/5 passed** | **0** | **50,482 / 28,297** |

All five specs passed the Judge on the first attempt. No retries were needed.

---

### claude-haiku-4-5

| Spec | Score | Tests | Judge retries | Tokens (in/out) |
|---|---|---|---|---|
| is_prime | **9.3/10** | PASSED ✅ | 0 | 4,618 / 2,578 |
| expr_parser | **7.5/10** | FAILED ❌ | 2 | 20,562 / 17,820 |
| lru_cache | **8.8/10** | FAILED ❌ | 2 | 29,637 / 17,655 |
| trie | **6.5/10** | FAILED ❌ | 2 | 34,888 / 19,978 |
| graph | **8.0/10** | PASSED ✅ | 0 | 11,069 / 6,634 |
| **Average** | **8.0/10** | **2/5 passed** | **1.2 avg** | **100,774 / 64,665** |

Haiku hit the 2-retry ceiling on the three hardest specs and still failed. The Judge's
correction hints were detailed and accurate — the model simply couldn't fix subtle
recursive logic bugs (LRU list invariants, Trie `delete` return value, parser precedence)
within the retry budget.

---

### Head-to-head comparison

| Metric | claude-opus-4-6 | claude-haiku-4-5 |
|---|---|---|
| Pass rate | **5/5 (100%)** | 2/5 (40%) |
| Avg score | **9.1/10** | 8.0/10 |
| Avg judge retries | **0** | 1.2 |
| Total tokens (5 runs) | 78,779 | 165,439 |
| Relative token cost | **1×** | ~2.1× more tokens |

> Opus produces higher-quality code on the first pass, avoiding the retry loops that
> inflate Haiku's token count on complex specs. For hard data-structure problems,
> Opus 4.6 is both more reliable and more token-efficient than Haiku 4.5 despite
> its higher per-token price.

---

## Cost

| Model | Approx cost per simple run | Approx cost per complex run |
|---|---|---|
| claude-opus-4-6 | ~$0.04 | ~$0.15 |
| claude-haiku-4-5 | ~$0.01 | ~$0.10–0.20 (retries inflate cost) |

Pass `--model <model-id>` to select the model at runtime:
```bash
python cli.py review --spec "..." --name foo --model claude-haiku-4-5-20251001
python cli.py review --spec "..." --name foo --model claude-opus-4-6
```

---

## Built by

Aditya Shah — [LinkedIn](https://linkedin.com/in/aditya-r-shah26)
