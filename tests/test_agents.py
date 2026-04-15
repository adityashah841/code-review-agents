"""
Unit tests for agent classes.
Mocks the Anthropic client so no real API calls are made.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


def make_mock_client(response_text: str):
    """Return a mock Anthropic client that returns response_text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_msg.usage.input_tokens = 10
    mock_msg.usage.output_tokens = 20
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestBaseAgent:
    def test_validate_python_syntax_valid(self):
        from agents.base_agent import BaseAgent
        ok, err = BaseAgent.validate_python_syntax("def f(x: int) -> int:\n    return x")
        assert ok is True
        assert err == ""

    def test_validate_python_syntax_invalid(self):
        from agents.base_agent import BaseAgent
        ok, err = BaseAgent.validate_python_syntax("def f( return")
        assert ok is False
        assert "SyntaxError" in err

    def test_write_and_read_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from agents.base_agent import BaseAgent
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = make_mock_client("hello")
            agent = BaseAgent("test", "sys", "sk-ant-fake123")
        path = agent.write_file("test_out.py", "x = 1")
        content = agent.read_file(path)
        assert content == "x = 1"

    def test_retry_on_connection_error(self):
        import anthropic
        from agents.base_agent import BaseAgent
        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                anthropic.APIConnectionError(request=MagicMock()),
                MagicMock(
                    content=[MagicMock(text="ok")],
                    usage=MagicMock(input_tokens=5, output_tokens=5),
                ),
            ]
            mock_cls.return_value = mock_client
            with patch("time.sleep"):
                agent = BaseAgent("test", "sys", "sk-ant-fake123")
                result = agent.call("hello", max_retries=3)
        assert result == "ok"


class TestSpecAgent:
    def test_expand_returns_dict(self):
        from agents.spec_agent import SpecAgent
        contract = {
            "function_name": "sort_list",
            "description": "Sort a list",
            "args": [],
            "returns": {"type": "list", "description": "sorted"},
            "raises": [],
            "edge_cases": [],
            "example_call": "sort_list([3,1,2])",
            "example_output": "[1,2,3]",
        }
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = make_mock_client(json.dumps(contract))
            agent = SpecAgent("sk-ant-fake123")
            result = agent.expand("sort a list")
        assert result["function_name"] == "sort_list"

    def test_expand_strips_markdown_fences(self):
        from agents.spec_agent import SpecAgent
        contract = {"function_name": "f", "description": "d",
                    "args": [], "returns": {"type": "None", "description": ""},
                    "raises": [], "edge_cases": [],
                    "example_call": "f()", "example_output": "None"}
        fenced = f"```json\n{json.dumps(contract)}\n```"
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = make_mock_client(fenced)
            agent = SpecAgent("sk-ant-fake123")
            result = agent.expand("some spec")
        assert result["function_name"] == "f"


class TestReviewerAgent:
    def test_review_returns_parsed_dict(self):
        from agents.reviewer_agent import ReviewerAgent
        review = {
            "scores": {"correctness": 8, "security": 9,
                       "style": 7, "complexity": 8},
            "issues": [],
            "summary": "Good code.",
            "recommendations": ["Add more tests"],
        }
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = make_mock_client(json.dumps(review))
            agent = ReviewerAgent("sk-ant-fake123")
            with patch.object(agent, "read_file", return_value="def f(): pass"):
                result = agent.review("workspace/f.py")
        assert result["scores"]["correctness"] == 8


class TestJudgeAgent:
    def test_syntax_error_caught_without_api_call(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from agents.judge_agent import JudgeAgent
        os.makedirs("workspace", exist_ok=True)
        bad_code_path = "workspace/bad.py"
        with open(bad_code_path, "w") as f:
            f.write("def f( return")
        test_path = "workspace/test_bad.py"
        with open(test_path, "w") as f:
            f.write("def test_f(): pass")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent = JudgeAgent("sk-ant-fake123")
            verdict = agent.evaluate({}, bad_code_path, {}, test_path, "", 1)
        assert verdict["overall_pass"] is False
        assert verdict["agents"]["coder"]["pass"] is False
        mock_cls.return_value.messages.create.assert_not_called()
