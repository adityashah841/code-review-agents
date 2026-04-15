import re
from .base_agent import BaseAgent

CODER_SYSTEM = """You are an expert Python software engineer.
Given a precise function contract (JSON), write clean, production-quality Python.

Rules:
- Use type hints on all arguments and return value
- Include a Google-style docstring
- stdlib only — no external dependencies
- No print statements
- No global state
- Handle every edge case listed in the contract
- Return ONLY the Python code — no markdown fences, no explanation"""


class CoderAgent(BaseAgent):
    """
    Generates a Python module from an expanded spec contract.
    The generated code is written to workspace/<module_name>.py
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-5"):
        super().__init__("Coder", CODER_SYSTEM, api_key, model=model)

    def generate(self, spec_contract: dict, module_name: str,
                 stream: bool = False,
                 correction_hint: str = "") -> str:
        """
        Generate code from spec_contract.
        correction_hint is populated by the Judge on retry runs.
        Returns the path to the written file.
        """
        import json
        prompt = f"Function contract:\n{json.dumps(spec_contract, indent=2)}"
        if correction_hint:
            prompt += f"\n\nPrevious attempt was rejected by the Judge.\n" \
                      f"Correction required: {correction_hint}\n" \
                      f"Fix all issues described above."

        code = self.call(prompt, stream=stream)
        # Strip accidental markdown fences
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("```").strip()
        return self.write_file(f"{module_name}.py", code)
