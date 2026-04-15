"""
Smoke test for the orchestrator pipeline using fully mocked agents.
Verifies the control flow without making real API calls.
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def make_mock_agents(judge_pass=True, retries_needed=0):
    """Return mock instances for all 5 agents."""
    spec = MagicMock()
    spec.expand.return_value = {
        "function_name": "sort_list",
        "description": "Sort a list",
        "args": [], "returns": {"type": "list", "description": ""},
        "raises": [], "edge_cases": [],
        "example_call": "sort_list([3,1,2])",
        "example_output": "[1,2,3]",
    }
    spec.total_input_tokens = spec.total_output_tokens = 0

    coder = MagicMock()
    coder.generate.return_value = "workspace/sorter.py"
    coder.total_input_tokens = coder.total_output_tokens = 0

    reviewer = MagicMock()
    reviewer.review.return_value = {
        "scores": {"correctness": 9, "security": 9,
                   "style": 8, "complexity": 8},
        "issues": [], "summary": "Good.", "recommendations": [],
    }
    reviewer.total_input_tokens = reviewer.total_output_tokens = 0

    tester = MagicMock()
    tester.generate_tests.return_value = "workspace/test_sorter.py"
    tester.total_input_tokens = tester.total_output_tokens = 0

    judge = MagicMock()
    if retries_needed == 0:
        judge.evaluate.return_value = {
            "overall_pass": True,
            "agents": {
                "coder":    {"pass": True, "reason": None},
                "reviewer": {"pass": True, "reason": None},
                "tester":   {"pass": True, "reason": None},
            },
            "summary": "All good.",
        }
    else:
        fail_verdict = {
            "overall_pass": False,
            "agents": {
                "coder":    {"pass": False, "reason": "Logic error"},
                "reviewer": {"pass": True, "reason": None},
                "tester":   {"pass": True, "reason": None},
            },
            "summary": "Coder failed.",
        }
        pass_verdict = {
            "overall_pass": True,
            "agents": {
                "coder":    {"pass": True, "reason": None},
                "reviewer": {"pass": True, "reason": None},
                "tester":   {"pass": True, "reason": None},
            },
            "summary": "All good.",
        }
        judge.evaluate.side_effect = [fail_verdict, pass_verdict]
    judge.total_input_tokens = judge.total_output_tokens = 0
    judge.MAX_RETRIES = 2

    return spec, coder, reviewer, tester, judge


def test_pipeline_happy_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os; os.makedirs("workspace", exist_ok=True)
    with open("workspace/sorter.py", "w") as f:
        f.write("def sort_list(lst): return sorted(lst)")
    with open("workspace/test_sorter.py", "w") as f:
        f.write("def test_sort(): assert True")

    spec, coder, reviewer, tester, judge = make_mock_agents()

    judge_cls = MagicMock(return_value=judge, MAX_RETRIES=2)
    with patch("orchestrator.SpecAgent", return_value=spec), \
         patch("orchestrator.CoderAgent", return_value=coder), \
         patch("orchestrator.ReviewerAgent", return_value=reviewer), \
         patch("orchestrator.TesterAgent", return_value=tester), \
         patch("orchestrator.JudgeAgent", judge_cls), \
         patch("orchestrator.save_run"), \
         patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0,
                                           stdout="1 passed", stderr="")
        result = asyncio.run(
            __import__("orchestrator").run_pipeline(
                "sort a list", "sorter", "sk-ant-fake123"
            )
        )

    assert result["tests_passed"] is True
    assert result["judge_retries"] == 0


def test_pipeline_judge_retry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os; os.makedirs("workspace", exist_ok=True)
    with open("workspace/sorter.py", "w") as f:
        f.write("def sort_list(lst): return sorted(lst)")
    with open("workspace/test_sorter.py", "w") as f:
        f.write("def test_sort(): assert True")

    spec, coder, reviewer, tester, judge = make_mock_agents(retries_needed=1)

    judge_cls = MagicMock(return_value=judge, MAX_RETRIES=2)
    with patch("orchestrator.SpecAgent", return_value=spec), \
         patch("orchestrator.CoderAgent", return_value=coder), \
         patch("orchestrator.ReviewerAgent", return_value=reviewer), \
         patch("orchestrator.TesterAgent", return_value=tester), \
         patch("orchestrator.JudgeAgent", judge_cls), \
         patch("orchestrator.save_run"), \
         patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0,
                                           stdout="1 passed", stderr="")
        result = asyncio.run(
            __import__("orchestrator").run_pipeline(
                "sort a list", "sorter", "sk-ant-fake123"
            )
        )

    assert result["judge_retries"] == 1
    assert coder.generate.call_count == 2
