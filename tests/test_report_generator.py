"""Tests for report_generator.generate_report."""
import os
import pytest


def make_result(tests_passed=True, retries=0):
    return {
        "module_name": "sorter",
        "raw_spec": "sort a list",
        "spec_contract": {"function_name": "sort_list"},
        "code_path": "workspace/sorter.py",
        "review": {
            "scores": {"correctness": 9, "security": 8,
                       "style": 7, "complexity": 8},
            "issues": [
                {"line": 3, "severity": "low",
                 "category": "style", "message": "missing blank line"},
            ],
            "summary": "Good overall.",
            "recommendations": ["Add docstring"],
        },
        "test_path": "workspace/test_sorter.py",
        "test_stdout": "1 passed in 0.01s",
        "tests_passed": tests_passed,
        "judge_verdict": {"overall_pass": True},
        "judge_retries": retries,
        "total_input_tokens": 100,
        "total_output_tokens": 200,
    }


def test_report_is_written(tmp_path):
    from report_generator import generate_report
    out = str(tmp_path / "report.md")
    generate_report(make_result(), out)
    assert os.path.exists(out)
    content = open(out).read()
    assert "sorter" in content
    assert "PASSED" in content


def test_report_contains_scores(tmp_path):
    from report_generator import generate_report
    out = str(tmp_path / "report.md")
    generate_report(make_result(), out)
    content = open(out).read()
    assert "Correctness" in content
    assert "9/10" in content


def test_report_failed_tests(tmp_path):
    from report_generator import generate_report
    out = str(tmp_path / "report.md")
    generate_report(make_result(tests_passed=False), out)
    content = open(out).read()
    assert "FAILED" in content


def test_report_retries_shown(tmp_path):
    from report_generator import generate_report
    out = str(tmp_path / "report.md")
    generate_report(make_result(retries=2), out)
    content = open(out).read()
    assert "**Judge retries:** 2" in content
