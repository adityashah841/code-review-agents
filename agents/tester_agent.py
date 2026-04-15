import re
from .base_agent import BaseAgent

TESTER_SYSTEM = """You are a pytest expert and QA engineer.
Given a Python module and its function contract, write a complete pytest test file.

Rules:
- Import the module using: from workspace.<module_name> import <function_name>
- Write tests for: happy path, edge cases, error/exception cases
- Use descriptive test function names: test_<what>_<condition>
- Each test must have a docstring explaining what it verifies
- Use pytest.raises() for exception tests
- Do not use mocks — test real behavior
- Return ONLY the pytest code — no markdown fences, no explanation"""


class TesterAgent(BaseAgent):
    """
    Generates a pytest test file for the generated code.
    The test file is written to workspace/test_<module_name>.py
    and is then executed by the orchestrator.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-5"):
        super().__init__("Tester", TESTER_SYSTEM, api_key, model=model)

    def generate_tests(self, code_path: str, module_name: str,
                       spec_contract: dict,
                       correction_hint: str = "") -> str:
        """
        Generate tests for the code at code_path.
        correction_hint is populated by the Judge on retry runs.
        Returns the path to the written test file.
        """
        import json
        code = self.read_file(code_path)
        prompt = (
            f"Module name: {module_name}\n\n"
            f"Function contract:\n{json.dumps(spec_contract, indent=2)}\n\n"
            f"Code to test:\n{code}"
        )
        if correction_hint:
            prompt += f"\n\nPrevious test file was rejected by the Judge.\n" \
                      f"Issue to fix: {correction_hint}"

        tests = self.call(prompt)
        tests = re.sub(r"```(?:python)?", "", tests).strip().rstrip("```").strip()
        return self.write_file(f"test_{module_name}.py", tests)
