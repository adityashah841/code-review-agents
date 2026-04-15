import json
import re
import ast
import subprocess
import sys
from .base_agent import BaseAgent

JUDGE_SYSTEM = """You are a strict quality assurance judge for an automated
code generation pipeline. You receive:
1. The original function spec contract
2. Generated Python code
3. A code review (JSON)
4. A pytest test file
5. The actual test execution results

Your job is to detect any of these failure modes:
- The code has logic errors that contradict the spec
- The tests import a function or module that does not match the actual generated code
- The tests test the wrong behavior (hallucinated function signatures)
- The review references line numbers that do not exist in the code
- The tests would never pass even if the code is correct (flawed test logic)
- Any agent has ignored its correction hint from a previous retry

Return ONLY valid JSON with exactly this schema:
{
  "overall_pass": true|false,
  "agents": {
    "coder": {
      "pass": true|false,
      "reason": "brief explanation or null if pass"
    },
    "reviewer": {
      "pass": true|false,
      "reason": "brief explanation or null if pass"
    },
    "tester": {
      "pass": true|false,
      "reason": "brief explanation or null if pass"
    }
  },
  "summary": "one sentence describing the overall result"
}

Be strict. If a test imports 'sorter.sort_integers' but the code defines 'sort_list',
that is a tester failure. If the review mentions line 47 but the code is 20 lines long,
that is a reviewer failure."""


class JudgeAgent(BaseAgent):
    """
    Supervises Coder, Reviewer, and Tester outputs.
    Runs free syntax checks first (no API call), then uses the LLM
    to check semantic alignment between all three outputs.
    Returns a verdict dict indicating which agents pass/fail and why,
    enabling targeted retries rather than blanket re-runs.
    """

    MAX_RETRIES = 2

    def __init__(self, api_key: str):
        super().__init__("Judge", JUDGE_SYSTEM, api_key)

    def evaluate(
        self,
        spec_contract: dict,
        code_path: str,
        review: dict,
        test_path: str,
        test_stdout: str,
        test_returncode: int,
    ) -> dict:
        """
        Full evaluation pipeline:
        1. Free syntax check on generated code
        2. Free syntax check on test file
        3. LLM-based alignment check across all outputs
        Returns verdict dict.
        """
        code = self.read_file(code_path)
        tests = self.read_file(test_path)

        # --- Free checks (no API call) ---
        syntax_ok, syntax_err = self.validate_python_syntax(code)
        if not syntax_ok:
            return {
                "overall_pass": False,
                "agents": {
                    "coder": {"pass": False, "reason": syntax_err},
                    "reviewer": {"pass": True, "reason": None},
                    "tester": {"pass": True, "reason": None},
                },
                "summary": f"Coder produced syntactically invalid Python: {syntax_err}",
            }

        test_syntax_ok, test_syntax_err = self.validate_python_syntax(tests)
        if not test_syntax_ok:
            return {
                "overall_pass": False,
                "agents": {
                    "coder": {"pass": True, "reason": None},
                    "reviewer": {"pass": True, "reason": None},
                    "tester": {"pass": False, "reason": test_syntax_err},
                },
                "summary": f"Tester produced syntactically invalid pytest file: {test_syntax_err}",
            }

        # --- LLM alignment check ---
        prompt = (
            f"SPEC CONTRACT:\n{json.dumps(spec_contract, indent=2)}\n\n"
            f"GENERATED CODE ({code_path}):\n{code}\n\n"
            f"REVIEW:\n{json.dumps(review, indent=2)}\n\n"
            f"TEST FILE ({test_path}):\n{tests}\n\n"
            f"TEST EXECUTION RESULT (returncode={test_returncode}):\n{test_stdout}"
        )
        raw = self.call(prompt)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
        return json.loads(raw)
