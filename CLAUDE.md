# CLAUDE.md — code-review-agents

Detailed project reference for AI-assisted development sessions.

---

## What this project is

`code-review-agents` is a Python CLI tool that takes a plain-English function description
and runs it through a fully automated, self-correcting multi-agent pipeline. The output is:

- A generated Python module in `workspace/<name>.py`
- A pytest test file in `workspace/test_<name>.py`
- A structured Markdown review report in `reports/<name>.md`
- A SQLite history entry in `runs.db`

The pipeline uses five AI agents, each backed by the Anthropic API (claude-opus-4-5),
with the user supplying their own API key at runtime. No key is ever stored to disk.

---

## Repository

- **GitHub:** https://github.com/adityashah841/code-review-agents
- **Owner:** adityashah841
- **Visibility:** Public
- **CI:** GitHub Actions on every push to `main` (`.github/workflows/ci.yml`)

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 (pinned via `.python-version`) |
| Package manager | `uv` (pyproject.toml + uv.lock) |
| AI API | Anthropic SDK (`anthropic` package), model `claude-opus-4-5` |
| CLI framework | `click` (group with `review` and `history` subcommands) |
| Terminal UI | `rich` (panels, tables, status spinners) |
| Testing | `pytest` (unit tests with mocks — no real API calls) |
| History storage | SQLite via `sqlite3` stdlib (file: `runs.db`) |
| Async | `asyncio` (Reviewer + Tester run in parallel via `asyncio.gather`) |
| Containerisation | Docker + docker-compose |

---

## Project structure

```
code-review-agents/
├── agents/
│   ├── __init__.py             Exports all 6 agent classes
│   ├── base_agent.py           BaseAgent: API wrapper, retry, streaming, token tracking
│   ├── spec_agent.py           SpecAgent: plain-English → JSON function contract
│   ├── coder_agent.py          CoderAgent: JSON contract → Python module
│   ├── reviewer_agent.py       ReviewerAgent: code → structured JSON review
│   ├── tester_agent.py         TesterAgent: code + contract → pytest file
│   └── judge_agent.py          JudgeAgent: validates all outputs, triggers retries
├── orchestrator.py             Async pipeline coordinator
├── cli.py                      Click CLI entry point (review + history commands)
├── report_generator.py         Converts result dict → Markdown report file
├── history.py                  SQLite init/save/query helpers
├── tests/
│   ├── __init__.py
│   ├── test_agents.py          Unit tests for BaseAgent, SpecAgent, ReviewerAgent, JudgeAgent
│   ├── test_report_generator.py Unit tests for generate_report()
│   └── test_orchestrator.py    Smoke tests for run_pipeline() control flow
├── workspace/                  Generated .py files land here (gitignored)
├── reports/                    Generated .md reports land here (gitignored)
├── .github/workflows/ci.yml    GitHub Actions CI
├── Dockerfile                  python:3.11-slim, uv, ENTRYPOINT cli.py
├── docker-compose.yml          Mounts workspace/, reports/, runs.db
├── pyproject.toml              uv project config + dependencies
├── uv.lock                     Locked dependency tree
├── .python-version             Pins Python 3.11
├── .gitignore                  Excludes .venv, __pycache__, workspace/*.py, reports/*.md, runs.db
└── CLAUDE.md                   This file
```

---

## The five agents

### BaseAgent (`agents/base_agent.py`)
The shared base class all agents inherit from.

**Key responsibilities:**
- Holds the `anthropic.Anthropic` client (constructed with the caller-supplied `api_key`)
- `call(user_msg, max_retries=3, stream=False)` — main entry point with exponential backoff
- `_call_blocking()` — standard create call, accumulates `total_input_tokens` / `total_output_tokens`
- `_call_streaming()` — streams token-by-token to stdout, accumulates usage from `get_final_message()`
- `write_file(filename, content)` — writes to `workspace/` directory, returns path
- `read_file(path)` — reads and returns file content
- `validate_python_syntax(code)` — static method, uses `ast.parse()`, returns `(bool, error_str)`, **free** (no API call)
- Retry handles `APIStatusError` (401 → immediate re-raise as `ValueError`) and `APIConnectionError`
- Default model: `claude-opus-4-5`

### SpecAgent (`agents/spec_agent.py`)
Converts a plain-English description into a precise JSON function contract.

**Output schema:**
```json
{
  "function_name": "snake_case_name",
  "description": "one sentence",
  "args": [{"name": "...", "type": "...", "description": "..."}],
  "returns": {"type": "...", "description": "..."},
  "raises": ["ExceptionType: when"],
  "edge_cases": ["list of edge cases"],
  "example_call": "function_name(args)",
  "example_output": "expected output string"
}
```

**`expand(raw_spec)`** — calls the model, strips markdown fences, `json.loads()`, returns dict.

### CoderAgent (`agents/coder_agent.py`)
Generates a Python module from the spec contract.

**`generate(spec_contract, module_name, stream=False, correction_hint="")`**
- Builds prompt from JSON contract + optional `correction_hint` (populated by Judge on retry)
- Strips accidental markdown fences from response
- Writes to `workspace/<module_name>.py`
- Returns the file path

**Rules enforced via system prompt:** type hints, Google-style docstrings, stdlib-only, no print statements, no global state, handle all edge cases.

### ReviewerAgent (`agents/reviewer_agent.py`)
Reviews the generated code and returns structured JSON.

**Output schema:**
```json
{
  "scores": {"correctness": 0-10, "security": 0-10, "style": 0-10, "complexity": 0-10},
  "issues": [{"line": int, "severity": "low|medium|high", "category": "...", "message": "..."}],
  "summary": "paragraph",
  "recommendations": ["top 3 improvements"]
}
```

**`review(code_path, correction_hint="")`** — reads the file, calls the model, returns parsed dict.

### TesterAgent (`agents/tester_agent.py`)
Generates a complete pytest file for the generated code.

**`generate_tests(code_path, module_name, spec_contract, correction_hint="")`**
- Imports are generated as `from workspace.<module_name> import <function_name>`
- Covers: happy path, edge cases, exception cases
- No mocks — tests real behavior
- Writes to `workspace/test_<module_name>.py`
- Returns the file path

### JudgeAgent (`agents/judge_agent.py`)
Supervises all three outputs and returns a verdict.

**`evaluate(spec_contract, code_path, review, test_path, test_stdout, test_returncode)`**

Two-phase evaluation:
1. **Free phase** — `ast.parse()` on both code and test file. If either has a syntax error,
   returns an immediate verdict without any API call.
2. **LLM phase** — sends all five artefacts to the model, which checks:
   - Code logic matches the spec
   - Test imports match the actual function/module names in the code
   - Reviewer line numbers are valid for the code length
   - Test logic is not inherently broken

**Verdict schema:**
```json
{
  "overall_pass": true|false,
  "agents": {
    "coder":    {"pass": bool, "reason": "string or null"},
    "reviewer": {"pass": bool, "reason": "string or null"},
    "tester":   {"pass": bool, "reason": "string or null"}
  },
  "summary": "one sentence"
}
```

**`MAX_RETRIES = 2`** — class-level constant used by the orchestrator retry loop.

---

## Orchestrator (`orchestrator.py`)

`run_pipeline(raw_spec, module_name, api_key, stream_coder=False, console=None)` is an
`async` function. Call with `asyncio.run(run_pipeline(...))` from the CLI.

**Pipeline steps:**
1. `SpecAgent.expand()` — synchronous, run via `asyncio.to_thread`
2. `CoderAgent.generate()` — synchronous, run via `asyncio.to_thread`
3. **Loop** (max `JudgeAgent.MAX_RETRIES + 1` iterations = 3 total attempts):
   a. If previous Judge verdict failed coder: re-run `CoderAgent.generate()` with hint
   b. `asyncio.gather(ReviewerAgent.review, TesterAgent.generate_tests)` — **parallel**
   c. `subprocess.run(pytest ...)` — execute test file, capture stdout/stderr
   d. `JudgeAgent.evaluate()` — validate all outputs
   e. If `overall_pass=True`: break
   f. Else: extract per-agent correction hints, increment `judge_retries`, continue
4. Aggregate token usage across all 5 agents
5. `save_run()` to SQLite history
6. Return full result dict

**Result dict keys:**
`module_name`, `raw_spec`, `spec_contract`, `code_path`, `review`, `test_path`,
`test_stdout`, `tests_passed`, `judge_verdict`, `judge_retries`,
`total_input_tokens`, `total_output_tokens`

---

## CLI (`cli.py`)

Entry point: `python cli.py` (or `uv run python cli.py`)

### `review` command
```
python cli.py review [OPTIONS]
  -s, --spec TEXT      Plain-English function spec  [required]
  -n, --name TEXT      Output module name  [default: module]
  -o, --output TEXT    Markdown report path  [default: reports/review.md]
  -k, --api-key TEXT   Anthropic API key (or set ANTHROPIC_API_KEY env var)
  --stream             Stream Coder output token-by-token
  -y, --yes            Skip spec confirmation prompt
```

Calls `asyncio.run(run_pipeline(...))`, then calls `generate_report(result, output)`,
then prints a Rich score table and test status summary.

### `history` command
```
python cli.py history [OPTIONS]
  -n, --limit INTEGER  Number of recent runs  [default: 20]
```

Calls `get_history(limit)` and renders a Rich table.

### `validate_api_key(api_key)`
Called at the top of `review` before anything else. Raises `click.UsageError` if:
- Key is empty
- Key does not start with `sk-ant-`

---

## Report generator (`report_generator.py`)

`generate_report(result, output_path)` writes a Markdown file with:
- Header: module name, timestamp, spec, test status, Judge retry count, token usage
- Score table: correctness / security / style / complexity with ratings
- Summary paragraph from the reviewer
- Issues grouped by severity (high → medium → low) with line numbers
- Top recommendations
- Full pytest stdout
- Expanded spec contract JSON

---

## History (`history.py`)

SQLite database at `runs.db` (gitignored). Schema:

```sql
CREATE TABLE runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT,
    raw_spec            TEXT,
    module_name         TEXT,
    avg_score           REAL,
    tests_passed        INTEGER,
    judge_retries       INTEGER,
    total_input_tokens  INTEGER,
    total_output_tokens INTEGER,
    report_path         TEXT
)
```

Functions: `init_db()`, `save_run(...)`, `get_history(limit=20) → list[dict]`

---

## Tests (`tests/`)

All tests mock the Anthropic client — **no real API calls are made**. Run with:
```bash
uv run pytest tests/ -v --no-header
```

14 tests across 3 files:

| File | Tests |
|---|---|
| `test_agents.py` | BaseAgent syntax validation, file I/O, retry on connection error; SpecAgent JSON parsing + fence stripping; ReviewerAgent dict parsing; JudgeAgent free syntax check short-circuits API |
| `test_report_generator.py` | Report written to disk, contains scores, reflects FAILED status, shows retry count |
| `test_orchestrator.py` | Happy path (judge passes immediately); retry path (judge fails once, coder re-runs, passes on second attempt) |

**Critical test detail:** `JudgeAgent.MAX_RETRIES` is a class-level attribute accessed as
`JudgeAgent.MAX_RETRIES` in the orchestrator. In tests, the mock class must have
`MAX_RETRIES=2` set on it (not just the instance): `MagicMock(return_value=judge, MAX_RETRIES=2)`.

---

## Key design decisions

1. **API key never stored** — passed as a CLI option or read from `ANTHROPIC_API_KEY` env var
   at startup, held in memory only for the duration of the run.

2. **Free syntax checks before LLM** — `ast.parse()` catches obvious coder/tester failures
   without spending tokens. Only proceeds to the LLM alignment check if both files are
   syntactically valid.

3. **Targeted retries, not blanket re-runs** — the Judge verdict identifies which specific
   agent(s) failed. Only those agents are retried with a correction hint. Other agents'
   outputs are reused.

4. **Parallel Reviewer + Tester** — `asyncio.gather()` runs both simultaneously. Wall-clock
   time equals `max(reviewer_time, tester_time)`, not their sum.

5. **Correction hints** — when the Judge rejects an agent's output, the reason string is
   passed back to that agent on the next attempt as `correction_hint`. This gives the model
   targeted guidance rather than a blind retry.

6. **`asyncio.to_thread`** — all synchronous agent calls are wrapped in `asyncio.to_thread`
   so the async event loop stays unblocked and `asyncio.gather` works correctly.

---

## Common commands

```bash
# Run tests
uv run pytest tests/ -v --no-header

# Run a live review (requires ANTHROPIC_API_KEY)
uv run python cli.py review --spec "check if a number is prime" --name is_prime

# Stream coder output
uv run python cli.py review --spec "merge two sorted lists" --name merge --stream

# View run history
uv run python cli.py history

# Docker (requires Docker installed)
export ANTHROPIC_API_KEY="sk-ant-..."
docker compose run review --spec "sort a list" --name sorter
```

---

## Known limitations / future work

- The `workspace/` generated files use `from workspace.<module>` imports, which requires
  running pytest from the project root with `workspace/` on `sys.path`. The orchestrator
  handles this via `sys.path.insert(0, os.getcwd())`.
- Docker is defined but requires Docker Desktop to be installed to run locally.
- The `report_path` column in `runs.db` is always saved as `""` — the CLI generates the
  report after `save_run()` is called. A future improvement would update the row after
  writing the report.
- `--yes` flag skips spec confirmation, but confirmation is currently post-hoc (shown after
  the pipeline completes) rather than before. This is by design per the original spec.
