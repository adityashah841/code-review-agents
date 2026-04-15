import json
import re
from .base_agent import BaseAgent

SPEC_SYSTEM = """You are a software requirements analyst.
Given a plain-English description of a Python function, produce a precise,
structured function contract in JSON.

Return ONLY valid JSON with exactly this schema:
{
  "function_name": "snake_case_name",
  "description": "one sentence description",
  "args": [
    {"name": "arg_name", "type": "Python type hint", "description": "what it is"}
  ],
  "returns": {"type": "Python type hint", "description": "what is returned"},
  "raises": ["ExceptionType: when it is raised"],
  "edge_cases": ["list of edge cases the implementation must handle"],
  "example_call": "function_name(example_args)",
  "example_output": "expected output as a string"
}

No preamble. No explanation. Only the JSON object."""


class SpecAgent(BaseAgent):
    """
    Expands a plain-English spec into a structured function contract.
    The contract is shown to the user for confirmation before any code
    is generated, preventing wasted API calls on misunderstood specs.
    """

    def __init__(self, api_key: str):
        super().__init__("Spec", SPEC_SYSTEM, api_key)

    def expand(self, raw_spec: str) -> dict:
        """
        Takes a raw user spec like "sort a list of integers" and
        returns a structured dict describing the exact function contract.
        """
        raw = self.call(f"Spec: {raw_spec}")
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
        return json.loads(raw)
