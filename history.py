import sqlite3
import os
from datetime import datetime


DB_PATH = "runs.db"


def init_db():
    """Create the runs table if it does not exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            raw_spec    TEXT    NOT NULL,
            module_name TEXT    NOT NULL,
            avg_score   REAL,
            tests_passed INTEGER,
            judge_retries INTEGER,
            total_input_tokens  INTEGER,
            total_output_tokens INTEGER,
            report_path TEXT
        )
    """)
    con.commit()
    con.close()


def save_run(
    raw_spec: str,
    module_name: str,
    avg_score: float,
    tests_passed: bool,
    judge_retries: int,
    total_input_tokens: int,
    total_output_tokens: int,
    report_path: str,
):
    """Save a completed pipeline run to the local SQLite database."""
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            None,
            datetime.now().isoformat(timespec="seconds"),
            raw_spec,
            module_name,
            round(avg_score, 2),
            int(tests_passed),
            judge_retries,
            total_input_tokens,
            total_output_tokens,
            report_path,
        ),
    )
    con.commit()
    con.close()


def get_history(limit: int = 20) -> list[dict]:
    """Return the last `limit` runs as a list of dicts."""
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]
